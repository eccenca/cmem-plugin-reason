"""Ontology consistency validation workflow plugin module"""

from collections import OrderedDict
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from cmem.cmempy.dp.proxy.graph import get_graph_import_tree, get_graphs_list, get_streamed
from cmem_plugin_base.dataintegration.context import ExecutionContext, ExecutionReport
from cmem_plugin_base.dataintegration.description import Icon, Plugin, PluginParameter
from cmem_plugin_base.dataintegration.entity import Entities, Entity, EntityPath, EntitySchema
from cmem_plugin_base.dataintegration.parameter.choice import ChoiceParameterType
from cmem_plugin_base.dataintegration.plugins import WorkflowPlugin
from cmem_plugin_base.dataintegration.ports import FixedNumberOfInputs, FixedSchemaPort
from cmem_plugin_base.dataintegration.types import BoolParameterType
from cmem_plugin_base.dataintegration.utils import setup_cmempy_user_access

from cmem_plugin_reason.doc import VALIDATE_DOC
from cmem_plugin_reason.utils import (
    IGNORE_MISSING_IMPORTS_PARAMETER,
    MAX_RAM_PERCENTAGE_DEFAULT,
    MAX_RAM_PERCENTAGE_PARAMETER,
    ONTOLOGY_GRAPH_IRI_PARAMETER,
    cancel_workflow,
    create_xml_catalog_file,
    eccenca_reasoner,
    is_valid_uri,
)

LABEL = "Validate OWL consistency"

VALIDATE_REASONERS = OrderedDict(
    {
        "elk": "ELK",
        "elk_emr": "ELK (EMR)",
        "hermit": "HermiT",
        "jfact": "JFact",
    }
)

VALIDATE_PROFILES_PARAMETER = PluginParameter(
    param_type=BoolParameterType(),
    name="validate_profile",
    label="Validate OWL2 profiles",
    description="""Validate the input ontology against OWL profiles (DL, EL, QL, RL, and Full) and
    annotate the result graph.""",
    default_value=False,
)


def validate_profiles(plugin: WorkflowPlugin, graphs: dict) -> list[str]:
    """Validate OWL2 profiles.

    The reasoner jar checks the whole imports closure (imports resolved via the catalog),
    so no separate "merge" step is needed. It prints the profiles the ontology conforms to
    to stdout, one per line, in the order Full, DL, EL, QL, RL.
    """
    ontology_location = f"{plugin.temp}/{graphs[plugin.ontology_graph_iri]}"
    catalog_location = f"{plugin.temp}/catalog-v001.xml"
    cmd = [
        "validate-profile",
        "--input",
        ontology_location,
        "--catalog",
        catalog_location,
    ]
    response = eccenca_reasoner(cmd, plugin.max_ram_percentage)
    if response.returncode != 0:
        message = response.stderr.decode().strip() or response.stdout.decode().strip()
        raise OSError(message)
    return response.stdout.decode().split()


@Plugin(
    label=LABEL,
    description="Validates the consistency of an OWL ontology.",
    documentation=VALIDATE_DOC,
    icon=Icon(file_name="file-icons--owl.svg", package=__package__),
    parameters=[
        IGNORE_MISSING_IMPORTS_PARAMETER,
        ONTOLOGY_GRAPH_IRI_PARAMETER,
        MAX_RAM_PERCENTAGE_PARAMETER,
        VALIDATE_PROFILES_PARAMETER,
        PluginParameter(
            param_type=ChoiceParameterType(VALIDATE_REASONERS),
            name="reasoner",
            label="Reasoner",
            description="Reasoner option.",
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

    def __init__(  # noqa: PLR0913
        self,
        ontology_graph_iri: str,
        ignore_missing_imports: bool = False,
        reasoner: str = "hermit",
        mode: str = "inconsistency",
        validate_profile: bool = False,
        stop_at_inconsistencies: bool = False,
        max_ram_percentage: int = MAX_RAM_PERCENTAGE_DEFAULT,
    ) -> None:
        errors = ""
        if not is_valid_uri(ontology_graph_iri):
            errors += 'Invalid IRI for parameter "Ontology graph IRI." '
        if reasoner not in VALIDATE_REASONERS:
            errors += 'Invalid value for parameter "Reasoner". '
        if mode not in ("inconsistency", "unsatisfiability"):
            errors += 'Invalid value for parameter "Mode". '
        if max_ram_percentage not in range(1, 101):
            errors += 'Invalid value for parameter "Maximum RAM Percentage". '
        if errors:
            raise ValueError(errors[:-1])
        self.ontology_graph_iri = ontology_graph_iri
        self.reasoner = reasoner
        self.mode = mode
        self.stop_at_inconsistencies = stop_at_inconsistencies
        self.md_filename = "mdfile.md"
        self.validate_profile = validate_profile
        self.max_ram_percentage = max_ram_percentage
        self.ignore_missing_imports = ignore_missing_imports

        self.label = LABEL

        self.input_ports = FixedNumberOfInputs([])
        self.schema = self.generate_output_schema()
        self.output_port = FixedSchemaPort(self.schema)

    def generate_output_schema(self) -> EntitySchema:
        """Generate output entity schema."""
        paths = [
            EntityPath("explanation"),
            EntityPath("ontology_graph_iri"),
            EntityPath("reasoner"),
        ]
        if self.validate_profile:
            paths.append(EntityPath("profiles"))
        return EntitySchema(type_uri="validate", paths=paths)

    def get_graphs(self, graphs: dict, missing: list) -> None:
        """Get graphs from CMEM"""
        for iri, filename in graphs.items():
            self.log.info(f"Fetching graph {iri}.")
            with (Path(self.temp) / filename).open("w", encoding="utf-8") as file:
                if iri not in missing:
                    self.log.info(f"Fetching graph {iri}.")
                    setup_cmempy_user_access(self.context.user)
                    file.write(get_streamed(iri).text)

    def get_graphs_tree(self) -> tuple[dict, list]:
        """Get graph import tree."""
        missing = []
        graphs = {}
        if self.ontology_graph_iri not in graphs:
            graphs[self.ontology_graph_iri] = f"{uuid4().hex}.nt"
            tree = get_graph_import_tree(self.ontology_graph_iri)
            for value in tree["tree"].values():
                for iri in value:
                    if iri not in graphs:
                        if iri not in self.graphs_dict:
                            missing.append(iri)
                        graphs[iri] = f"{uuid4().hex}.nt"
        if missing:
            if self.ignore_missing_imports:
                [self.log.warning(f"Missing graph import: {iri}") for iri in missing]
            else:
                raise ImportError(f"Missing graph imports: {', '.join(missing)}")

        return graphs, missing

    def explain(self, graphs: dict) -> None:
        """Reason"""
        data_location = f"{self.temp}/{graphs[self.ontology_graph_iri]}"
        catalog_location = f"{self.temp}/catalog-v001.xml"
        cmd = [
            "explain",
            "--input",
            data_location,
            "--reasoner",
            self.reasoner,
            "-M",
            self.mode,
            "--catalog",
            catalog_location,
            "--explanation",
            f"{self.temp}/{self.md_filename}",
        ]
        response = eccenca_reasoner(cmd, self.max_ram_percentage)
        if response.returncode != 0:
            message = (
                response.stderr.decode().strip()
                or response.stdout.decode().strip()
                or "reasoner error"
            )
            raise OSError(message)

    def make_entities(self, text: str, valid_profiles: list) -> Entities:
        """Make entities"""
        values = [[text], [self.ontology_graph_iri], [self.reasoner]]
        if self.validate_profile:
            values.append(valid_profiles)
        entities = [
            Entity(
                uri="https://eccenca.com/plugin_validateontology/result",
                values=values,
            ),
        ]
        return Entities(entities=entities, schema=self.schema)

    def _execute(self) -> Entities | None:
        """Run the workflow operator."""
        setup_cmempy_user_access(self.context.user)
        graphs, missing = self.get_graphs_tree()
        self.get_graphs(graphs, missing)
        if cancel_workflow(self):
            return None
        create_xml_catalog_file(self.temp, graphs)
        self.explain(graphs)
        if cancel_workflow(self):
            return None
        valid_profiles = validate_profiles(self, graphs) if self.validate_profile else []
        if cancel_workflow(self):
            return None

        text = (Path(self.temp) / self.md_filename).read_text()
        if text.split("\n", 1)[0] != "No explanations found.":
            if self.stop_at_inconsistencies:
                self.context.report.update(
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
            self.context.report.update(
                ExecutionReport(
                    operation="validate",
                    operation_desc="ontology validated.",
                    entity_count=1,
                )
            )
        return self.make_entities(text, valid_profiles)

    def execute(self, inputs: Sequence[Entities], context: ExecutionContext) -> Entities | None:  # noqa: ARG002
        """Execute plugin with temporary directory"""
        setup_cmempy_user_access(context.user)
        self.graphs_dict = {_["iri"]: _ for _ in get_graphs_list()}
        if self.ontology_graph_iri not in self.graphs_dict:
            raise ValueError(f"Ontology graph does not exist: {self.ontology_graph_iri}")

        self.context = context
        context.report.update(
            ExecutionReport(
                operation="validate",
                operation_desc="ontologies validated.",
            )
        )

        with TemporaryDirectory() as self.temp:
            return self._execute()
