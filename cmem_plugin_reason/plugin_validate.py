"""Ontology consistency validation workflow plugin module"""

from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import time

import validators.url
from cmem.cmempy.dp.proxy.graph import get
from cmem.cmempy.workspace.projects.resources.resource import create_resource
from cmem_plugin_base.dataintegration.context import ExecutionContext, ExecutionReport
from cmem_plugin_base.dataintegration.description import Icon, Plugin, PluginParameter
from cmem_plugin_base.dataintegration.entity import Entities, Entity, EntityPath, EntitySchema
from cmem_plugin_base.dataintegration.parameter.choice import ChoiceParameterType
from cmem_plugin_base.dataintegration.parameter.graph import GraphParameterType
from cmem_plugin_base.dataintegration.plugins import WorkflowPlugin
from cmem_plugin_base.dataintegration.ports import FixedNumberOfInputs, FixedSchemaPort
from cmem_plugin_base.dataintegration.types import BoolParameterType, StringParameterType
from cmem_plugin_base.dataintegration.utils import setup_cmempy_user_access
from pathvalidate import is_valid_filename

from cmem_plugin_reason.doc import VALIDATE_DOC
from cmem_plugin_reason.utils import (
    MAX_RAM_PERCENTAGE_DEFAULT,
    MAX_RAM_PERCENTAGE_PARAMETER,
    ONTOLOGY_GRAPH_IRI_PARAMETER,
    REASONER_PARAMETER,
    REASONERS,
    VALIDATE_PROFILES_PARAMETER,
    create_xml_catalog_file,
    get_graphs_tree,
    get_output_graph_label,
    get_provenance,
    post_profiles,
    post_provenance,
    robot,
    send_result,
    validate_profiles,
)


@Plugin(
    label="Validate OWL consistency",
    description="Validates the consistency of an OWL ontology.",
    documentation=VALIDATE_DOC,
    icon=Icon(file_name="file-icons--owl.svg", package=__package__),
    parameters=[
        ONTOLOGY_GRAPH_IRI_PARAMETER,
        MAX_RAM_PERCENTAGE_PARAMETER,
        VALIDATE_PROFILES_PARAMETER,
        REASONER_PARAMETER,
        PluginParameter(
            param_type=StringParameterType(),
            name="md_filename",
            label="Output filename",
            description="The filename of the Markdown file with the explanation of "
            "inconsistencies.⚠️ Existing files will be overwritten.",
            default_value="",
        ),
        PluginParameter(
            param_type=GraphParameterType(
                allow_only_autocompleted_values=False,
                classes=[
                    "https://vocab.eccenca.com/di/Dataset",
                    "http://rdfs.org/ns/void#Dataset",
                    "http://www.w3.org/2002/07/owl#Ontology",
                ],
            ),
            name="output_graph_iri",
            label="Output graph IRI",
            description="""The IRI of the output graph for the inconsistency validation. ⚠️ Existing
            graphs will be overwritten.""",
            default_value="",
        ),
        PluginParameter(
            param_type=BoolParameterType(),
            name="stop_at_inconsistencies",
            label="Stop at inconsistencies",
            description="Raise an error if inconsistencies are found. If enabled, the plugin does "
            "not output entities.",
            default_value=False,
        ),
        PluginParameter(
            param_type=BoolParameterType(),
            name="output_entities",
            label="Output entities",
            description="""Output entities. The plugin outputs the explanation as text in Markdown
            format on the path "markdown", the ontology IRI on the path "ontology_graph_iri", the
            reasoner option on the path "reasoner", and, if enabled, the valid OWL2 profiles on the
            path "valid_profiles".""",
            default_value=False,
        ),
        PluginParameter(
            param_type=ChoiceParameterType(
                OrderedDict(
                    {
                        "inconsistency": "inconsistency",
                        "unsatisfiability": "unsatisfiability",
                    }
                )
            ),
            name="mode",
            label="Mode",
            description="""Mode "inconsistency" generates an explanation for an inconsistent
            ontology. Mode "unsatisfiability" generates explanations for many unsatisfiable classes
            at once.""",
            default_value="inconsistency",
        ),
    ],
)
class ValidatePlugin(WorkflowPlugin):
    """Validate plugin"""

    def __init__(  # noqa: PLR0912 PLR0913 C901
        self,
        ontology_graph_iri: str,
        reasoner: str,
        output_graph_iri: str = "",
        md_filename: str = "",
        mode: str = "inconsistency",
        validate_profile: bool = False,
        output_entities: bool = False,
        stop_at_inconsistencies: bool = False,
        max_ram_percentage: int = MAX_RAM_PERCENTAGE_DEFAULT,
    ) -> None:
        errors = ""
        if not validators.url(ontology_graph_iri):
            errors += 'Invalid IRI for parameter "Ontology graph IRI." '
        if output_graph_iri and not validators.url(output_graph_iri):
            errors += 'Invalid IRI for parameter "Output graph IRI". '
        if output_graph_iri and output_graph_iri == ontology_graph_iri:
            errors += "Output graph IRI cannot be the same as the Ontology graph IRI. "
        if reasoner not in REASONERS:
            errors += 'Invalid value for parameter "Reasoner". '
        if md_filename and not is_valid_filename(md_filename):
            errors += 'Invalid filename for parameter "Output filename". '
        if not output_graph_iri and not md_filename and not output_entities:
            errors += "No output selected. "
        if mode not in ("inconsistency", "unsatisfiability"):
            errors += 'Invalid value for parameter "Mode". '
        if max_ram_percentage not in range(1, 101):
            errors += 'Invalid value for parameter "Maximum RAM Percentage". '
        if errors:
            raise ValueError(errors[:-1])
        self.ontology_graph_iri = ontology_graph_iri
        self.reasoner = reasoner
        self.output_graph_iri = output_graph_iri
        self.mode = mode
        self.stop_at_inconsistencies = stop_at_inconsistencies
        if md_filename:
            self.md_filename = md_filename
            self.write_md = True
        else:
            self.md_filename = "mdfile.md"
            self.write_md = False
        self.validate_profile = validate_profile
        self.output_entities = output_entities
        self.max_ram_percentage = max_ram_percentage

        self.input_ports = FixedNumberOfInputs([])
        if self.output_entities:
            self.schema = self.generate_output_schema()
            self.output_port = FixedSchemaPort(self.schema)
        else:
            self.output_port = None

    def generate_output_schema(self) -> EntitySchema | None:
        """Generate output entity schema."""
        paths = [EntityPath("markdown"), EntityPath("ontology_graph_iri"), EntityPath("reasoner")]
        if self.validate_profile:
            paths.append(EntityPath("valid_profiles"))
        return EntitySchema(type_uri="validate", paths=paths)

    def get_graphs(self, graphs: dict, context: ExecutionContext) -> None:
        """Get graphs from CMEM"""
        for iri, filename in graphs.items():
            self.log.info(f"Fetching graph {iri}.")
            with (Path(self.temp) / filename).open("w", encoding="utf-8") as file:
                setup_cmempy_user_access(context.user)
                file.write(get(iri).text)

    def explain(self, graphs: dict) -> None:
        """Reason"""
        data_location = f"{self.temp}/{graphs[self.ontology_graph_iri]}"
        utctime = str(datetime.fromtimestamp(int(time()), tz=UTC))[:-6].replace(" ", "T") + "Z"
        label = get_output_graph_label(self.ontology_graph_iri, "Validation Result")
        cmd = (
            f'explain --input "{data_location}" '
            f"--reasoner {self.reasoner} -M {self.mode} "
            f'--explanation "{self.temp}/{self.md_filename}"'
        )
        if self.output_graph_iri:
            cmd += (
                f' annotate --ontology-iri "{self.output_graph_iri}" '
                f'--language-annotation rdfs:label "{label}" en '
                f"--language-annotation rdfs:comment "
                f'"Ontology validation of <{self.ontology_graph_iri}>" en '
                f'--link-annotation dc:source "{self.ontology_graph_iri}" '
                f'--typed-annotation dc:created "{utctime}" xsd:dateTime '
                f'--output "{self.temp}/output.ttl"'
            )
        response = robot(cmd, self.max_ram_percentage)
        if response.returncode != 0:
            if response.stdout:
                raise OSError(response.stdout.decode())
            if response.stderr:
                raise OSError(response.stderr.decode())
            raise OSError("ROBOT error")

    def make_resource(self, context: ExecutionContext) -> None:
        """Make MD resource in project"""
        create_resource(
            project_name=context.task.project_id(),
            resource_name=self.md_filename,
            file_resource=(Path(self.temp) / self.md_filename).open("r", encoding="utf-8"),
            replace=True,
        )

    def add_profiles(self, valid_profiles: list) -> list:
        """Add profile validation result to output"""
        with (Path(self.temp) / self.md_filename).open("a", encoding="utf-8") as mdfile:
            mdfile.write("\n\n\n# Valid Profiles:\n")
            if valid_profiles:
                profiles_str = "\n- ".join(valid_profiles)
                mdfile.write(f"- {profiles_str}\n")
        if self.output_graph_iri:
            post_profiles(self, valid_profiles)
        return valid_profiles

    def make_entities(self, text: str, valid_profiles: list) -> Entities:
        """Make entities"""
        values = [[text], [self.ontology_graph_iri], [self.reasoner]]
        if self.validate_profile:
            values.append([",".join(valid_profiles)])
        entities = [
            Entity(
                uri="https://eccenca.com/plugin_validateontology/result",
                values=values,
            ),
        ]
        return Entities(entities=entities, schema=self.schema)

    def _execute(self, context: ExecutionContext) -> Entities | None:
        """Run the workflow operator."""
        setup_cmempy_user_access(context.user)
        graphs = get_graphs_tree((self.ontology_graph_iri, self.output_graph_iri))
        self.get_graphs(graphs, context)
        create_xml_catalog_file(self.temp, graphs)
        self.explain(graphs)

        if self.output_graph_iri:
            setup_cmempy_user_access(context.user)
            send_result(self.output_graph_iri, Path(self.temp) / "output.ttl")
            setup_cmempy_user_access(context.user)
            post_provenance(self, get_provenance(self, "Validate", context))

        valid_profiles = (
            self.add_profiles(validate_profiles(self, graphs)) if self.validate_profile else []
        )

        if self.write_md:
            setup_cmempy_user_access(context.user)
            self.make_resource(context)

        text = (Path(self.temp) / self.md_filename).read_text()
        if text.split("\n", 1)[0] != "No explanations found.":
            if self.stop_at_inconsistencies:
                context.report.update(
                    ExecutionReport(
                        operation="validate",
                        error="Inconsistencies found in ontology.",
                        operation_desc="ontologies processed.",
                        entity_count=1,
                    )
                )
            else:
                self.log.warning("Inconsistencies found in ontology.")
        else:
            context.report.update(
                ExecutionReport(
                    operation="validate",
                    operation_desc="ontology validated.",
                    entity_count=1,
                )
            )
        if self.output_entities:
            return self.make_entities(text, valid_profiles)
        return None

    def execute(self, inputs: None, context: ExecutionContext) -> Entities | None:  # noqa: ARG002
        """Execute plugin with temporary directory"""
        context.report.update(
            ExecutionReport(
                operation="validate",
                operation_desc="ontologies validated.",
            )
        )
        with TemporaryDirectory() as self.temp:
            return self._execute(context)
