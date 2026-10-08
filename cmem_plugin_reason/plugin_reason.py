"""Reasoning workflow plugin module"""

from collections import OrderedDict
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from cmem_plugin_base.dataintegration.client import get_client
from cmem_plugin_base.dataintegration.context import ExecutionContext, ExecutionReport
from cmem_plugin_base.dataintegration.description import Icon, Plugin, PluginParameter
from cmem_plugin_base.dataintegration.parameter.choice import ChoiceParameterType
from cmem_plugin_base.dataintegration.parameter.graph import GraphParameterType
from cmem_plugin_base.dataintegration.plugins import WorkflowPlugin
from cmem_plugin_base.dataintegration.ports import FixedNumberOfInputs
from cmem_plugin_base.dataintegration.types import BoolParameterType

from cmem_plugin_reason.doc import REASON_DOC
from cmem_plugin_reason.utils import (
    CATALOG_FILENAME,
    DI_DATASET,
    IGNORE_MISSING_IMPORTS_PARAMETER,
    MAX_RAM_PERCENTAGE_DEFAULT,
    MAX_RAM_PERCENTAGE_PARAMETER,
    ONTOLOGY_GRAPH_IRI_PARAMETER,
    OWL_IMPORTS,
    OWL_ONTOLOGY,
    RESULT_FILENAME,
    VOID_DATASET,
    build_annotation_nt,
    cancel_workflow,
    create_xml_catalog_file,
    eccenca_reasoner,
    get_graph_as_file,
    get_output_graph_label,
    is_valid_uri,
    post_provenance,
    raise_on_error,
    send_result,
    skolem_args,
)

LABEL = "Reason"

SKOLEMIZE_DESC = """Replace the blank nodes of the result (e.g. for inferred class expressions
such as `p some B` or inverse properties) with IRIs, so no information is lost if the result is
processed by tools that do not keep blank nodes. The IRIs are UUIDs computed from the content and
the output graph, so re-running the task produces the same IRIs. ⚠️ The result is then no longer
valid OWL 2 in RDF; tools that read it as an ontology may misinterpret these nodes."""

REASON_REASONERS = OrderedDict(
    {
        "elk": "ELK",
        "elk_emr": "ELK (EMR)",
        "hermit": "HermiT",
        "jfact": "JFact",
        "structural": "Structural Reasoner",
    }
)


SUBCLASS_DESC = """The reasoner will infer assertions about the hierarchy of classes, i.e.
`SubClassOf:` statements.\n
If there are classes `Person`, `Student` and `Professor`, such that `Person DisjointUnionOf:
Student, Professor` holds, the reasoner will infer `Student SubClassOf: Person`.
The Structural Reasoner only uses asserted hierarchies, so it does not infer this.
"""

EQUIVALENCE_DESC = """The reasoner will infer assertions about the equivalence of named classes,
i.e. `EquivalentTo:` statements. Equivalences to class expressions are not inferred.\n
If there are classes `Pupil` and `Learner`, such that `Pupil SubClassOf: Learner` and `Learner
SubClassOf: Pupil` holds, the reasoner will infer `Pupil EquivalentTo: Learner`.
"""

DISJOINT_DESC = """The reasoner will infer assertions about the disjointness of classes, i.e.
`DisjointClasses:` statements.\n
If there are classes `Person`, `Student` and `Professor`, such that `Person DisjointUnionOf:
Student, Professor` holds, the reasoner will infer `DisjointClasses: Student, Professor`.
**Not supported by ELK or ELK (EMR).**
The Structural Reasoner only uses asserted hierarchies, so it does not infer this.
"""

DATA_PROP_CHAR_DESC = """The reasoner will infer characteristics of data properties, i.e.
`Characteristics:` statements. For data properties, this only pertains to functionality.\n
If there are data properties `identifier` and `enrollmentNumber`, such that `enrollmentNumber
SubPropertyOf: identifier` and `identifier Characteristics: Functional` holds, the reasoner will
infer `enrollmentNumber Characteristics: Functional`. ELK and ELK (EMR) ignore functional properties
(they are outside OWL 2 EL), so they do not infer this.
The Structural Reasoner only uses asserted hierarchies, so it does not infer this.
"""

DATA_PROP_EQUIV_DESC = """The reasoner will infer axioms about the equivalence of data properties,
 i.e. `EquivalentProperties` statements.\n
If there are data properties `identifier` and `enrollmentNumber`, such that `enrollmentNumber
SubPropertyOf: identifier` and `identifier SubPropertyOf: enrollmentNumber` holds, the reasoner
will infer `EquivalentProperties: identifier, enrollmentNumber`.
**Not supported by ELK or ELK (EMR).**
"""

DATA_PROP_SUB_DESC = """The reasoner will infer axioms about the hierarchy of data properties,
i.e. `SubPropertyOf:` statements.\n
If there are data properties `identifier`, `studentIdentifier` and `enrollmentNumber`, such that
`studentIdentifier SubPropertyOf: identifier` and `enrollmentNumber SubPropertyOf:
studentIdentifier` holds, the reasoner will infer `enrollmentNumber SubPropertyOf: identifier`.
**Not supported by ELK or ELK (EMR).**
"""

CLASS_ASSERT_DESC = """The reasoner will infer assertions about the classes of individuals, i.e.
`Types:` statements.\n
Assume, there are classes `Person`, `Student` and `University` as well as the property
`enrolledIn`, such that `Student EquivalentTo: Person and enrolledIn some University` holds. For
the individual `John` with the assertions `John Types: Person; Facts: enrolledIn
LeipzigUniversity`, the reasoner will infer `John Types: Student`.
The Structural Reasoner only uses asserted hierarchies, so it does not infer this.
"""

PROPERTY_ASSERT_DESC = """The reasoner will infer assertions about the properties of individuals,
i.e. `Facts:` statements.\n
Assume, there are properties `enrolled`, `enrolledIn` and `offers`, such that `enrolled
SubPropertyChain: enrolledIn o inverse (offers)` holds. For the individuals `John` and
`LeipzigUniversity` with the assertions `John Facts: enrolledIn KnowledgeRepresentation` and
`LeipzigUniversity Facts: offers KnowledgeRepresentation`, the reasoner will infer `John Facts:
enrolled LeipzigUniversity`.
**Not supported by ELK or ELK (EMR).**
The Structural Reasoner only uses asserted hierarchies, so it does not infer this.
"""

OBJECT_PROP_CHAR_DESC = """The reasoner will infer characteristics of object properties, i.e.
`Characteristics:` statements.\n
If there are object properties `enrolledIn` and `studentOf`, such that `enrolledIn
SubPropertyOf: studentOf` and `studentOf Characteristics: Functional` holds, the reasoner will
infer `enrolledIn Characteristics: Functional`. ELK and ELK (EMR) ignore functional properties
(they are outside OWL 2 EL), so they do not infer this.
The Structural Reasoner only uses asserted hierarchies, so it does not infer this.
"""

OBJECT_PROP_EQUIV_DESC = """The reasoner will infer assertions about the equivalence of object
properties, i.e. `EquivalentTo:` statements.\n
If there are object properties `hasAlternativeLecture` and `hasSameTopicAs`, such that
`hasAlternativeLecture Characteristics: Symmetric` and `hasSameTopicAs InverseOf:
hasAlternativeLecture` holds, the reasoner will infer `EquivalentProperties:
hasAlternativeLecture, hasSameTopicAs`. ELK and ELK (EMR) ignore symmetric and inverse
properties (they are outside OWL 2 EL), so they do not infer this.
"""

OBJECT_PROP_SUB_DESC = """The reasoner will infer axioms about the inclusion of object properties,
i.e. `SubPropertyOf:` statements.\n
If there are object properties `enrolledIn`, `studentOf` and `hasStudent`, such that `enrolledIn
SubPropertyOf: studentOf` and `enrolledIn InverseOf: hasStudent` holds, the reasoner will infer
`hasStudent SubPropertyOf: inverse (studentOf)`. ELK and ELK (EMR) ignore inverse properties
(they are outside OWL 2 EL), so they do not infer this.
"""

OBJECT_PROP_INV_DESC = """The reasoner will infer axioms about the inversion about object
properties, i.e. `InverseOf:` statements.\n
If there is a object property `hasAlternativeLecture`, such that `hasAlternativeLecture
Characteristics: Symmetric` holds, the reasoner will infer `hasAlternativeLecture InverseOf:
hasAlternativeLecture`.
**Not supported by ELK or ELK (EMR).**
"""

OBJECT_PROP_RANGE_DESC = """The reasoner will infer axioms about the ranges of object properties,
i.e. `Range:` statements.\n
If there are classes `Student` and `Lecture` as wells as object properties `hasStudent` and
`enrolledIn`, such that `hasStudent Range: Student and enrolledIn some Lecture` holds, the
reasoner will infer `hasStudent Range: Student`.
**Not supported by ELK or ELK (EMR).**
The Structural Reasoner only uses asserted hierarchies, so it does not infer this.
"""

OBJECT_PROP_DOMAIN_DESC = """The reasoner will infer axioms about the domains of object
properties, i.e. `Domain:` statements.\n
If there are classes `Person`, `Student` and `Professor` as wells as the object property
`hasRoleIn`, such that `Professor SubClassOf: Person`, `Student SubClassOf: Person` and
`hasRoleIn Domain: Professor or Student` holds, the reasoner will infer `hasRoleIn Domain:
Person`.
**Not supported by ELK or ELK (EMR).**
The Structural Reasoner only uses asserted hierarchies, so it does not infer this.
"""


@Plugin(
    label=LABEL,
    icon=Icon(file_name="fluent--brain-circuit-24-regular.svg", package=__package__),
    description="Performs OWL reasoning.",
    documentation=REASON_DOC,
    parameters=[
        IGNORE_MISSING_IMPORTS_PARAMETER,
        ONTOLOGY_GRAPH_IRI_PARAMETER,
        MAX_RAM_PERCENTAGE_PARAMETER,
        PluginParameter(
            param_type=BoolParameterType(),
            name="skolemize",
            label="Replace blank nodes with IRIs",
            description=SKOLEMIZE_DESC,
            default_value=False,
            advanced=True,
        ),
        PluginParameter(
            param_type=ChoiceParameterType(REASON_REASONERS),
            name="reasoner",
            label="Reasoner",
            description="""Reasoner option. ELK and ELK (EMR) are limited to OWL 2 EL and support
            fewer axiom generators; the Structural Reasoner only uses asserted hierarchies. See the
            documentation for details.""",
        ),
        PluginParameter(
            param_type=GraphParameterType(classes=[OWL_ONTOLOGY, DI_DATASET, VOID_DATASET]),
            name="data_graph_iri",
            label="Data graph IRI",
            description="""The IRI of the input data graph. At least one of data graph and
            ontology graph must be specified.""",
        ),
        PluginParameter(
            param_type=GraphParameterType(
                allow_only_autocompleted_values=False,
                classes=[OWL_ONTOLOGY],
            ),
            name="output_graph_iri",
            label="Output graph IRI",
            description="""The IRI of the output graph for the reasoning result. ⚠️ Existing graphs
            will be overwritten.""",
        ),
        PluginParameter(
            param_type=BoolParameterType(),
            name="sub_class",
            label="Class inclusion (rdfs:subClassOf)",
            description=SUBCLASS_DESC,
            default_value=False,
        ),
        PluginParameter(
            param_type=BoolParameterType(),
            name="equivalent_class",
            label="Class equivalence (owl:equivalentClass)",
            description=EQUIVALENCE_DESC,
            default_value=False,
        ),
        PluginParameter(
            param_type=BoolParameterType(),
            name="disjoint_classes",
            label="Class disjointness (owl:disjointWith)",
            description=DISJOINT_DESC,
            default_value=False,
        ),
        PluginParameter(
            param_type=BoolParameterType(),
            name="data_property_characteristic",
            label="Data property characteristics",
            description=DATA_PROP_CHAR_DESC,
            default_value=False,
        ),
        PluginParameter(
            param_type=BoolParameterType(),
            name="equivalent_data_properties",
            label="Data property equivalence (owl:equivalentProperty)",
            description=DATA_PROP_EQUIV_DESC,
            default_value=False,
        ),
        PluginParameter(
            param_type=BoolParameterType(),
            name="sub_data_property",
            label="Data property inclusion (rdfs:subPropertyOf)",
            description=DATA_PROP_SUB_DESC,
            default_value=False,
        ),
        PluginParameter(
            param_type=BoolParameterType(),
            name="class_assertion",
            label="Individual class assertions (rdf:type)",
            description=CLASS_ASSERT_DESC,
            default_value=True,
        ),
        PluginParameter(
            param_type=BoolParameterType(),
            name="property_assertion",
            label="Individual property assertions",
            description=PROPERTY_ASSERT_DESC,
            default_value=True,
        ),
        PluginParameter(
            param_type=BoolParameterType(),
            name="equivalent_object_property",
            label="Object property equivalence (owl:equivalentProperty)",
            description=OBJECT_PROP_EQUIV_DESC,
            default_value=False,
        ),
        PluginParameter(
            param_type=BoolParameterType(),
            name="inverse_object_properties",
            label="Object property inversion (owl:inverseOf)",
            description=OBJECT_PROP_INV_DESC,
            default_value=False,
        ),
        PluginParameter(
            param_type=BoolParameterType(),
            name="object_property_characteristic",
            label="Object property characteristics",
            description=OBJECT_PROP_CHAR_DESC,
            default_value=False,
        ),
        PluginParameter(
            param_type=BoolParameterType(),
            name="sub_object_property",
            label="Object property inclusion (rdfs:subPropertyOf)",
            description=OBJECT_PROP_SUB_DESC,
            default_value=False,
        ),
        PluginParameter(
            param_type=BoolParameterType(),
            name="object_property_range",
            label="Object property ranges (rdfs:range)",
            description=OBJECT_PROP_RANGE_DESC,
            default_value=False,
        ),
        PluginParameter(
            param_type=BoolParameterType(),
            name="object_property_domain",
            label="Object property domains (rdfs:domain)",
            description=OBJECT_PROP_DOMAIN_DESC,
            default_value=False,
        ),
    ],
)
class ReasonPlugin(WorkflowPlugin):
    """Reason plugin"""

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        data_graph_iri: str = "",
        ontology_graph_iri: str = "",
        output_graph_iri: str = "",
        ignore_missing_imports: bool = False,
        reasoner: str = "hermit",
        class_assertion: bool = True,
        property_assertion: bool = True,
        sub_class: bool = False,
        equivalent_class: bool = False,
        disjoint_classes: bool = False,
        data_property_characteristic: bool = False,
        sub_object_property: bool = False,
        equivalent_object_property: bool = False,
        object_property_domain: bool = False,
        object_property_range: bool = False,
        object_property_characteristic: bool = False,
        inverse_object_properties: bool = False,
        sub_data_property: bool = False,
        equivalent_data_properties: bool = False,
        max_ram_percentage: int = MAX_RAM_PERCENTAGE_DEFAULT,
        skolemize: bool = False,
    ) -> None:
        #: Keyed by parameter name; camel_case() turns a key into the reasoner's generator name.
        self.axioms = {
            "sub_class": sub_class,
            "equivalent_class": equivalent_class,
            "disjoint_classes": disjoint_classes,
            "data_property_characteristic": data_property_characteristic,
            "equivalent_data_properties": equivalent_data_properties,
            "sub_data_property": sub_data_property,
            "class_assertion": class_assertion,
            "property_assertion": property_assertion,
            "equivalent_object_property": equivalent_object_property,
            "inverse_object_properties": inverse_object_properties,
            "object_property_characteristic": object_property_characteristic,
            "sub_object_property": sub_object_property,
            "object_property_range": object_property_range,
            "object_property_domain": object_property_domain,
        }
        self.data_graph_iri = data_graph_iri
        self.ontology_graph_iri = ontology_graph_iri
        self.output_graph_iri = output_graph_iri
        self.reasoner = reasoner
        self.max_ram_percentage = max_ram_percentage
        self.ignore_missing_imports = ignore_missing_imports
        self.skolemize = skolemize
        self.label = LABEL

        # expose the axiom generators as attributes too, so post_provenance() records them
        self.__dict__.update(self.axioms)

        self.input_ports = FixedNumberOfInputs([])
        self.output_port = None

    @property
    def input_graph_iris(self) -> list[str]:
        """The specified input graphs: data graph and/or ontology graph"""
        return [iri for iri in (self.data_graph_iri, self.ontology_graph_iri) if iri]

    @property
    def main_graph_iri(self) -> str:
        """The graph passed to the reasoner, importing the ontology if both are given"""
        return self.input_graph_iris[0]

    def graph_parameter_errors(self) -> str:
        """Check the graph IRI parameters, return the problems found"""
        errors = ""
        if not self.input_graph_iris:
            errors += "At least one of data graph IRI and ontology graph IRI must be specified. "
        if not self.output_graph_iri:
            errors += 'Parameter "Output graph IRI" must be specified. '
        graph_parameters = {
            "Data graph IRI": self.data_graph_iri,
            "Ontology graph IRI": self.ontology_graph_iri,
            "Output graph IRI": self.output_graph_iri,
        }
        for label, iri in graph_parameters.items():
            if iri and not is_valid_uri(iri):
                errors += f'Invalid IRI for parameter "{label}". '
        if self.output_graph_iri and self.output_graph_iri == self.data_graph_iri:
            errors += "Output graph IRI cannot be the same as the data graph IRI. "
        if self.output_graph_iri and self.output_graph_iri == self.ontology_graph_iri:
            errors += "Output graph IRI cannot be the same as the ontology graph IRI. "
        return errors

    def validate_parameters(self) -> None:
        """Validate the parameters, raise a ValueError listing all problems"""
        errors = self.graph_parameter_errors()
        if self.reasoner not in REASON_REASONERS:
            errors += 'Invalid value for parameter "Reasoner". '
        if True not in self.axioms.values():
            errors += "No axiom generator selected. "
        if self.max_ram_percentage not in range(1, 101):
            errors += 'Invalid value for parameter "Maximum RAM Percentage". '
        if errors:
            raise ValueError(errors[:-1])

    @staticmethod
    def camel_case(word: str) -> str:
        """Make an upper camel case axiom generator name from an underscored parameter name"""
        return "".join(part.title() for part in word.split("_"))

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
            if iri == self.data_graph_iri and self.ontology_graph_iri:
                with path.open("a", encoding="utf-8") as file:
                    file.write(f"\n<{iri}> <{OWL_IMPORTS}> <{self.ontology_graph_iri}> .")

    def get_graphs_tree(self) -> tuple[dict, list]:
        """Get graph import tree. Last item in graph_iris is output_graph_iri which is excluded"""
        missing = []
        graphs = {}
        for graph_iri in self.input_graph_iris:
            if graph_iri not in graphs:
                graphs[graph_iri] = f"{uuid4().hex}.nt"
                tree = self.client.graph_imports.get_import_tree(graph_iri).tree
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

    def reason(self, graphs: dict) -> None:
        """Reason"""
        axioms = " ".join(self.camel_case(k) for k, v in self.axioms.items() if v)
        data_location = f"{self.temp}/{graphs[self.main_graph_iri]}"
        catalog_location = f"{self.temp}/{CATALOG_FILENAME}"
        result_path = f"{self.temp}/{RESULT_FILENAME}"
        label = get_output_graph_label(self, self.main_graph_iri, "Reasoning Results")

        cmd = [
            "reason",
            "--input",
            data_location,
            "--reasoner",
            self.reasoner,
            "--axiom-generators",
            axioms,
            "--include-indirect",
            "true",
            "--exclude-duplicate-axioms",
            "true",
            "--exclude-owl-thing",
            "true",
            "--exclude-tautologies",
            "all",
            "--exclude-external-entities",
            "--catalog",
            catalog_location,
            "--output",
            result_path,
            "--reduce",
        ]
        if self.skolemize:
            cmd += skolem_args(self.output_graph_iri)
        response = eccenca_reasoner(cmd, self.max_ram_percentage)
        raise_on_error(response, "Reasoning")

        # Append annotation triples to the output file
        annotations = build_annotation_nt(
            graph_iri=self.output_graph_iri,
            label=label,
            comment=self.result_comment(),
            sources=self.input_graph_iris,
            rdf_type=OWL_ONTOLOGY,
        )
        with Path(result_path).open("a", encoding="utf-8") as f:
            f.write("\n" + annotations)

    def result_comment(self) -> str:
        """Describe the input graphs of the reasoning result"""
        if self.data_graph_iri and self.ontology_graph_iri:
            return (
                f"Reasoning results of data graph <{self.data_graph_iri}> "
                f"with ontology <{self.ontology_graph_iri}>"
            )
        if self.data_graph_iri:
            return f"Reasoning results of data graph <{self.data_graph_iri}>"
        return f"Reasoning results of ontology <{self.ontology_graph_iri}>"

    def _execute(self) -> None:
        """`Execute plugin"""
        graphs, missing = self.get_graphs_tree()
        self.get_graphs(graphs, missing)
        if cancel_workflow(self):
            return
        create_xml_catalog_file(self.temp, graphs)
        self.reason(graphs)
        if cancel_workflow(self):
            return
        send_result(self.client, self.output_graph_iri, Path(self.temp) / RESULT_FILENAME)
        post_provenance(self)

        self.context.report.update(
            ExecutionReport(
                operation="reason",
                operation_desc="ontology and data graph processed.",
                entity_count=1,
            )
        )

    def execute(self, inputs: Sequence, context: ExecutionContext) -> None:  # noqa: ARG002
        """Execute plugin with temporary directory"""
        self.validate_parameters()
        self.client = get_client(context)
        not_exist = [iri for iri in self.input_graph_iris if iri not in self.client.graphs]
        if not_exist:
            raise ValueError(f"Graphs do not exist: {', '.join(not_exist)}")

        self.context = context
        context.report.update(
            ExecutionReport(
                operation="reason",
                operation_desc="ontologies and data graphs processed.",
                entity_count=0,
            )
        )

        with TemporaryDirectory() as self.temp:
            self._execute()
