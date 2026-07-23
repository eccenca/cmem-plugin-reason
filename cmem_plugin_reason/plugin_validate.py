"""Ontology consistency validation workflow plugin module"""

from collections import OrderedDict
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from cmem_client.client import Client
from cmem_plugin_base.dataintegration.context import ExecutionContext, ExecutionReport
from cmem_plugin_base.dataintegration.description import Icon, Plugin, PluginParameter
from cmem_plugin_base.dataintegration.entity import Entities, Entity, EntityPath, EntitySchema
from cmem_plugin_base.dataintegration.parameter.choice import ChoiceParameterType
from cmem_plugin_base.dataintegration.parameter.graph import GraphParameterType
from cmem_plugin_base.dataintegration.plugins import WorkflowPlugin
from cmem_plugin_base.dataintegration.ports import FixedNumberOfInputs, FixedSchemaPort
from cmem_plugin_base.dataintegration.types import BoolParameterType, IntParameterType

from cmem_plugin_reason.doc import VALIDATE_DOC
from cmem_plugin_reason.utils import (
    IGNORE_MISSING_IMPORTS_PARAMETER,
    MAX_RAM_PERCENTAGE_DEFAULT,
    MAX_RAM_PERCENTAGE_PARAMETER,
    ONTOLOGY_GRAPH_IRI_PARAMETER,
    VALIDATE_PROFILES_PARAMETER,
    cancel_workflow,
    create_xml_catalog_file,
    eccenca_reasoner,
    get_graph_as_file,
    get_output_graph_label,
    is_valid_uri,
    post_provenance,
    send_result,
)

LABEL = "Validate OWL consistency"

#: Predicate used to annotate the output graph with the validated ontology's OWL 2
#: profiles. Specific to this plugin, so it lives here rather than in utils.py.
VALIDATE_PROFILE_PREDICATE = "https://vocab.eccenca.com/plugin/validate/profile"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
OWL_ONTOLOGY = "http://www.w3.org/2002/07/owl#Ontology"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
RDFS_COMMENT = "http://www.w3.org/2000/01/rdf-schema#comment"
DCTERMS_SOURCE = "http://purl.org/dc/terms/source"
DCTERMS_CREATED = "http://purl.org/dc/terms/created"

VALIDATE_REASONERS = OrderedDict(
    {
        "hermit": "HermiT",
        "jfact": "JFact",
    }
)


def _escape_nt_literal(text: str) -> str:
    """Escape a string for use in an N-Triples literal (backslash, quote, control chars)."""
    return (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def build_output_graph_nt(
    output_graph_iri: str,
    ontology_graph_iri: str,
    label: str,
    created: str,
    valid_profiles: list[str] | None,
) -> str:
    """Build the N-Triples annotation written to the output graph.

    Declares `output_graph_iri` as an owl:Ontology, gives it a human-readable
    rdfs:label/rdfs:comment, links it back to the validated ontology via
    dcterms:source, and records a dcterms:created timestamp. If profiles were
    validated, each conforming profile is added as a separate
    VALIDATE_PROFILE_PREDICATE triple. Written as plain N-Triples lines (full
    IRIs, no prefixes), same pattern used elsewhere for graph output, with
    literals escaped by hand rather than via an RDF library.
    """
    comment = _escape_nt_literal(f"Ontology validation of <{ontology_graph_iri}>")
    lines = [
        f"<{output_graph_iri}> <{RDF_TYPE}> <{OWL_ONTOLOGY}> .",
        f'<{output_graph_iri}> <{RDFS_LABEL}> "{_escape_nt_literal(label)}"@en .',
        f'<{output_graph_iri}> <{RDFS_COMMENT}> "{comment}"@en .',
        f"<{output_graph_iri}> <{DCTERMS_SOURCE}> <{ontology_graph_iri}> .",
        f"<{output_graph_iri}> <{DCTERMS_CREATED}> "
        f'"{created}"^^<http://www.w3.org/2001/XMLSchema#dateTime> .',
        f"<{ontology_graph_iri}> <{RDF_TYPE}> <{OWL_ONTOLOGY}> .",
    ]
    lines.extend(
        f'<{ontology_graph_iri}> <{VALIDATE_PROFILE_PREDICATE}> "{_escape_nt_literal(profile)}" .'
        for profile in valid_profiles or []
    )
    return "\n".join(lines) + "\n"


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
            description="""Optional IRI of an output graph to annotate with the validation
            result (label, comment, and a link back to the validated ontology). ⚠️ Existing
            graphs will be overwritten. Leave empty to skip.""",
            default_value="",
        ),
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
        PluginParameter(
            param_type=IntParameterType(),
            name="max_explanations",
            label="Maximum explanations",
            description="""The maximum number of independent explanations (justifications)
            generated per inference.""",
            default_value=1,
            advanced=True,
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
        max_explanations: int = 1,
        output_graph_iri: str = "",
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
        if max_explanations < 1:
            errors += 'Invalid value for parameter "Maximum explanations". '
        if output_graph_iri and not is_valid_uri(output_graph_iri):
            errors += 'Invalid IRI for parameter "Output graph IRI". '
        if output_graph_iri and output_graph_iri == ontology_graph_iri:
            errors += "Output graph IRI cannot be the same as the Ontology graph IRI. "
        if max_ram_percentage not in range(1, 101):
            errors += 'Invalid value for parameter "Maximum RAM Percentage". '
        if errors:
            raise ValueError(errors[:-1])
        self.ontology_graph_iri = ontology_graph_iri
        self.reasoner = reasoner
        self.mode = mode
        self.max_explanations = max_explanations
        self.output_graph_iri = output_graph_iri
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

    def validate_profiles(self, graphs: dict) -> list[str]:
        """Validate OWL2 profiles using the generic (bundled) reasoner jar.

        The reasoner jar checks the whole imports closure (imports resolved via the catalog),
        so no separate "merge" step is needed. It prints the profiles the ontology conforms to
        stdout, one per line, in the order Full, DL, EL, QL, RL.
        """
        ontology_location = f"{self.temp}/{graphs[self.ontology_graph_iri]}"
        catalog_location = f"{self.temp}/catalog-v001.xml"
        cmd = [
            "validate-profile",
            "--input",
            ontology_location,
            "--catalog",
            catalog_location,
        ]
        response = eccenca_reasoner(cmd, self.max_ram_percentage)
        if response.returncode != 0:
            message = response.stderr.decode().strip() or response.stdout.decode().strip()
            raise OSError(message)
        return response.stdout.decode().split()

    def get_graphs(self, graphs: dict, missing: list) -> None:
        """Get graphs from CMEM"""
        for iri, filename in graphs.items():
            path = Path(self.temp) / filename
            if iri in missing:
                # keep a placeholder file so the catalog can still reference it
                path.touch()
                continue
            self.log.info(f"Fetching graph {iri}.")
            get_graph_as_file(self.client, iri, path)

    def get_graphs_tree(self) -> tuple[dict, list]:
        """Get graph import tree."""
        missing = []
        graphs = {}
        if self.ontology_graph_iri not in graphs:
            graphs[self.ontology_graph_iri] = f"{uuid4().hex}.nt"
            tree = self.client.graph_imports.get_import_tree(self.ontology_graph_iri).tree
            for value in tree.values():
                for iri in value:
                    if iri not in graphs:
                        if iri == self.output_graph_iri:
                            raise ImportError("Input graph imports output graph.")
                        if iri not in self.client.graphs:
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
            "--max",
            str(self.max_explanations),
            "--catalog",
            catalog_location,
            "--explanation",
            f"{self.temp}/{self.md_filename}",
        ]
        if self.output_graph_iri:
            # Ask the jar to also save the loaded ontology as N-Triples; write_output_graph()
            # appends the label/comment/source/profile annotation onto this same file.
            cmd += ["--output", f"{self.temp}/result.nt", "--format", "nt"]
        response = eccenca_reasoner(cmd, self.max_ram_percentage)
        if response.returncode != 0:
            message = (
                response.stderr.decode().strip()
                or response.stdout.decode().strip()
                or "reasoner error"
            )
            raise OSError(message)

    def write_output_graph(self, valid_profiles: list[str]) -> None:
        """Append the validation-result annotation onto the ontology graph explain() wrote."""
        label = get_output_graph_label(self, self.ontology_graph_iri, "Validation Result")
        created = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        annotations = build_output_graph_nt(
            self.output_graph_iri,
            self.ontology_graph_iri,
            label,
            created,
            valid_profiles if self.validate_profile else None,
        )
        path = Path(self.temp) / "result.nt"
        with path.open("a", encoding="utf-8") as f:
            f.write("\n" + annotations)
        send_result(self.client, self.output_graph_iri, path)
        post_provenance(self)

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
        graphs, missing = self.get_graphs_tree()
        self.get_graphs(graphs, missing)
        if cancel_workflow(self):
            return None
        create_xml_catalog_file(self.temp, graphs)
        self.explain(graphs)
        if cancel_workflow(self):
            return None
        valid_profiles = self.validate_profiles(graphs) if self.validate_profile else []
        if cancel_workflow(self):
            return None

        if self.output_graph_iri:
            self.write_output_graph(valid_profiles)
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
        self.client = Client.from_context(context)
        if self.ontology_graph_iri not in self.client.graphs:
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
