"""Reasoning workflow plugin module"""

from collections import OrderedDict
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import time
from uuid import uuid4

from cmem_client.client import Client
from cmem_plugin_base.dataintegration.context import ExecutionContext, ExecutionReport
from cmem_plugin_base.dataintegration.description import Icon, Plugin, PluginParameter
from cmem_plugin_base.dataintegration.entity import Entities
from cmem_plugin_base.dataintegration.parameter.choice import ChoiceParameterType
from cmem_plugin_base.dataintegration.parameter.graph import GraphParameterType
from cmem_plugin_base.dataintegration.plugins import WorkflowPlugin
from cmem_plugin_base.dataintegration.ports import FixedNumberOfInputs
from cmem_plugin_base.dataintegration.types import BoolParameterType
from inflection import underscore

from cmem_plugin_reason.doc import REASON_DOC
from cmem_plugin_reason.utils import (
    IGNORE_MISSING_IMPORTS_PARAMETER,
    MAX_RAM_PERCENTAGE_DEFAULT,
    MAX_RAM_PERCENTAGE_PARAMETER,
    ONTOLOGY_GRAPH_IRI_PARAMETER,
    cancel_workflow,
    create_xml_catalog_file,
    eccenca_reasoner,
    get_graph_as_file,
    get_output_graph_label,
    is_valid_uri,
    post_provenance,
    send_result,
)

LABEL = "Reason"

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
"""

EQUIVALENCE_DESC = """The reasoner will infer assertions about the equivalence of classes, i.e.
`EquivalentTo:` statements.\n
If there are classes `Person`, `Student` and `Professor`, such that `Person DisjointUnionOf:
Student, Professor` holds, the reasoner will infer `Person EquivalentTo: Student and Professor`.
"""

DISJOINT_DESC = """The reasoner will infer assertions about the disjointness of classes, i.e.
`DisjointClasses:` statements.\n
If there are classes `Person`, `Student` and `Professor`, such that `Person DisjointUnionOf:
Student, Professor` holds, the reasoner will infer `DisjointClasses: Student, Professor`.
"""

DATA_PROP_CHAR_DESC = """The reasoner will infer characteristics of data properties, i.e.
`Characteristics:` statements. For data properties, this only pertains to functionality.\n
If there are data properties `identifier` and `enrollmentNumber`, such that `enrollmentNumber
SubPropertyOf: identifier` and `identifier Characteristics: Functional` holds, the reasoner will
infer `enrollmentNumber Characteristics: Functional`.
"""

DATA_PROP_EQUIV_DESC = """The reasoner will infer axioms about the equivalence of data properties,
 i.e. `EquivalentProperties` statements.\n
If there are data properties `identifier` and `enrollmentNumber`, such that `enrollmentNumber
SubPropertyOf: identifier` and `identifier SubPropertyOf: enrollmentNumber` holds, the reasoner
will infer `Student EquivalentProperties: identifier, enrollmentNumber`.
"""

DATA_PROP_SUB_DESC = """The reasoner will infer axioms about the hierarchy of data properties,
i.e. `SubPropertyOf:` statements.\n
If there are data properties `identifier`, `studentIdentifier` and `enrollmentNumber`, such that
`studentIdentifier SubPropertyOf: identifier` and `enrollmentNumber SubPropertyOf:
studentIdentifier` holds, the reasoner will infer `enrollmentNumber SubPropertyOf: identifier`.
"""

CLASS_ASSERT_DESC = """The reasoner will infer assertions about the classes of individuals, i.e.
`Types:` statements.\n
Assume, there are classes `Person`, `Student` and `University` as well as the property
`enrolledIn`, such that `Student EquivalentTo: Person and enrolledIn some University` holds. For
the individual `John` with the assertions `John Types: Person; Facts: enrolledIn
LeipzigUniversity`, the reasoner will infer `John Types: Student`.
"""

PROPERTY_ASSERT_DESC = """The reasoner will infer assertions about the properties of individuals,
i.e. `Facts:` statements.\n
Assume, there are properties `enrolledIn` and `offers`, such that `enrolled SubPropertyChain:
enrolledIn o inverse (offers)` holds. For the individuals `John`and `LeipzigUniversity` with the
assertions `John Facts: enrolledIn KnowledgeRepresentation` and `LeipzigUniversity Facts: offers
KnowledgeRepresentation`,  the reasoner will infer `John Facts: enrolledIn LeipzigUniversity`.
"""

OBJECT_PROP_CHAR_DESC = """The reasoner will infer characteristics of object properties, i.e.
`Characteristics:` statements.\n
If there are object properties `enrolledIn` and `studentOf`, such that `enrolledIn
SubPropertyOf: studentOf` and `enrolledIn Characteristics: Functional` holds, the reasoner will
infer `studentOf Characteristics: Functional`. **Note: this inference does neither work in JFact
nor in HermiT!**
"""

OBJECT_PROP_EQUIV_DESC = """The reasoner will infer assertions about the equivalence of object
properties, i.e. `EquivalentTo:` statements.\n
If there are object properties `hasAlternativeLecture` and `hasSameTopicAs`, such that
`hasAlternativeLecture Characteristics: Symmetric` and `hasSameTopicAs InverseOf:
hasAlternativeLecture` holds, the reasoner will infer `EquivalentProperties:
hasAlternativeLecture, hasSameTopicAs`.
"""

OBJECT_PROP_SUB_DESC = """The reasoner will infer axioms about the inclusion of object properties,
i.e. `SubPropertyOf:` statements.\n
If there are object properties `enrolledIn`, `studentOf` and `hasStudent`, such that `enrolledIn
SubPropertyOf: studentOf` and `enrolledIn InverseOf: hasStudent` holds, the reasoner will infer
`hasStudent SubPropertyOf: inverse (studentOf)`.
"""

OBJECT_PROP_INV_DESC = """The reasoner will infer axioms about the inversion about object
properties, i.e. `InverseOf:` statements.\n
If there is a object property `hasAlternativeLecture`, such that `hasAlternativeLecture
Characteristics: Symmetric` holds, the reasoner will infer `hasAlternativeLecture InverseOf:
hasAlternativeLecture`.
"""

OBJECT_PROP_RANGE_DESC = """The reasoner will infer axioms about the ranges of object properties,
i.e. `Range:` statements.\n
If there are classes `Student` and `Lecture` as wells as object properties `hasStudent` and
`enrolledIn`, such that `hasStudent Range: Student and enrolledIn some Lecture` holds, the
reasoner will infer `hasStudent Range: Student`.
"""

OBJECT_PROP_DOMAIN_DESC = """The reasoner will infer axioms about the domains of object
properties, i.e. `Domain:` statements.\n
If there are classes `Person`, `Student` and `Professor` as wells as the object property
`hasRoleIn`, such that `Professor SubClassOf: Person`, `Student SubClassOf: Person` and
`hasRoleIn Domain: Professor or Student` holds, the reasoner will infer `hasRoleIn Domain:
Person`.
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
            param_type=ChoiceParameterType(REASON_REASONERS),
            name="reasoner",
            label="Reasoner",
            description="Reasoner option.",
        ),
        PluginParameter(
            param_type=GraphParameterType(
                classes=[
                    "http://www.w3.org/2002/07/owl#Ontology",
                    "https://vocab.eccenca.com/di/Dataset",
                    "http://rdfs.org/ns/void#Dataset",
                ]
            ),
            name="data_graph_iri",
            label="Data graph IRI",
            description="The IRI of the input data graph.",
        ),
        PluginParameter(
            param_type=GraphParameterType(
                allow_only_autocompleted_values=False,
                classes=["http://www.w3.org/2002/07/owl#Ontology"],
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
        PluginParameter(
            param_type=BoolParameterType(),
            name="imports",
            label="Output graph import",
            description="""Add the triple <output_graph_iri> owl:imports <ontology_graph_iri> to the
            output graph.""",
            default_value=False,
        ),
    ],
)
class ReasonPlugin(WorkflowPlugin):
    """Reason plugin"""

    def __init__(  # noqa: PLR0913 C901
        self,
        data_graph_iri: str,
        ontology_graph_iri: str,
        ignore_missing_imports: bool = False,
        output_graph_iri: str | None = None,
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
        imports: bool = False,
        max_ram_percentage: int = MAX_RAM_PERCENTAGE_DEFAULT,
    ) -> None:
        self.axioms = {
            "SubClass": sub_class,
            "EquivalentClass": equivalent_class,
            "DisjointClasses": disjoint_classes,
            "DataPropertyCharacteristic": data_property_characteristic,
            "EquivalentDataProperties": equivalent_data_properties,
            "SubDataProperty": sub_data_property,
            "ClassAssertion": class_assertion,
            "PropertyAssertion": property_assertion,
            "EquivalentObjectProperty": equivalent_object_property,
            "InverseObjectProperties": inverse_object_properties,
            "ObjectPropertyCharacteristic": object_property_characteristic,
            "SubObjectProperty": sub_object_property,
            "ObjectPropertyRange": object_property_range,
            "ObjectPropertyDomain": object_property_domain,
        }
        errors = ""
        if not is_valid_uri(data_graph_iri):
            errors += 'Invalid IRI for parameter "Data graph IRI". '
        if not is_valid_uri(ontology_graph_iri):
            errors += 'Invalid IRI for parameter "Ontology graph IRI". '
        if not is_valid_uri(output_graph_iri):
            errors += 'Invalid IRI for parameter "Result graph IRI". '
        if output_graph_iri == data_graph_iri:
            errors += "Result graph IRI cannot be the same as the data graph IRI. "
        if output_graph_iri == ontology_graph_iri:
            errors += "Result graph IRI cannot be the same as the ontology graph IRI. "
        if reasoner not in REASON_REASONERS:
            errors += 'Invalid value for parameter "Reasoner". '
        if True not in self.axioms.values():
            errors += "No axiom generator selected. "
        if max_ram_percentage not in range(1, 101):
            errors += 'Invalid value for parameter "Maximum RAM Percentage". '
        if errors:
            raise ValueError(errors[:-1])

        self.data_graph_iri = data_graph_iri
        self.ontology_graph_iri = ontology_graph_iri
        self.output_graph_iri = output_graph_iri
        self.reasoner = reasoner
        self.imports = imports
        self.max_ram_percentage = max_ram_percentage
        self.ignore_missing_imports = ignore_missing_imports

        for k, v in self.axioms.items():
            self.__dict__[underscore(k)] = v

        self.data_imports_ontology = False
        self.label = LABEL
        self.input_ports = FixedNumberOfInputs([])
        self.output_port = None

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
            if iri == self.data_graph_iri:
                with path.open("a", encoding="utf-8") as file:
                    file.write(
                        f"\n<{iri}> "
                        "<http://www.w3.org/2002/07/owl#imports> "
                        f"<{self.ontology_graph_iri}> ."
                    )

    def get_graphs_tree(self) -> tuple[dict, list]:  # noqa: C901
        """Get graph import tree. Last item in graph_iris is output_graph_iri which is excluded"""
        missing = []
        graphs = {}
        for graph_iri in [self.data_graph_iri, self.ontology_graph_iri]:
            if graph_iri not in graphs:
                graphs[graph_iri] = f"{uuid4().hex}.nt"
                tree = self.client.graph_imports.get_import_tree(graph_iri).tree
                for value in tree.values():
                    for iri in value:
                        if iri not in graphs:
                            if iri == self.ontology_graph_iri:
                                self.data_imports_ontology = True
                            elif iri == self.output_graph_iri:
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
        axioms = " ".join(k for k, v in self.axioms.items() if v)
        data_location = f"{self.temp}/{graphs[self.data_graph_iri]}"
        catalog_location = f"{self.temp}/catalog-v001.xml"
        result_path = f"{self.temp}/result.nt"
        label = get_output_graph_label(self, self.data_graph_iri, "Reasoning Results")

        cmd = [
            "reason",
            "--input",
            str(data_location),
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
            str(catalog_location),
            "--output",
            str(result_path),
            "--reduce",
        ]
        response = eccenca_reasoner(cmd, self.max_ram_percentage)

        if response.returncode != 0:
            message = response.stderr.decode().strip() or response.stdout.decode().strip()
            raise OSError(message or "eccenca_reasoner error")

        # Append annotation triples to the output file
        utctime = str(datetime.fromtimestamp(int(time()), tz=UTC))[:-6].replace(" ", "T") + "Z"
        with open(result_path, "a", encoding="utf-8") as f:  # noqa: PTH123
            f.write(
                f"\n<{self.output_graph_iri}> "
                f"<http://www.w3.org/1999/02/22-rdf-syntax-ns#type> "
                f"<http://www.w3.org/2002/07/owl#Ontology> .\n"
                f"<{self.output_graph_iri}> "
                f"<http://www.w3.org/2000/01/rdf-schema#label> "
                f'"{label}"@en .\n'
                f"<{self.output_graph_iri}> "
                f"<http://www.w3.org/2000/01/rdf-schema#comment> "
                f'"Reasoning results of data graph <{self.data_graph_iri}> with ontology '
                f'<{self.ontology_graph_iri}>"@en .\n'
                f"<{self.output_graph_iri}> "
                f"<http://purl.org/dc/terms/source> "
                f"<{self.data_graph_iri}> .\n"
                f"<{self.output_graph_iri}> "
                f"<http://purl.org/dc/terms/source> "
                f"<{self.ontology_graph_iri}> .\n"
                f"<{self.output_graph_iri}> "
                f"<http://purl.org/dc/terms/created> "
                f'"{utctime}"^^<http://www.w3.org/2001/XMLSchema#dateTime> .\n'
            )

    def add_ontology_import(self) -> None:
        """Add ontology graph import to result graph"""
        query = f"""
            INSERT DATA {{
                GRAPH <{self.output_graph_iri}> {{
                    <{self.output_graph_iri}> <http://www.w3.org/2002/07/owl#imports>
                        <{self.ontology_graph_iri}>
                }}
            }}
        """
        self.client.store.sparql.update(query)

    def add_result_import(self) -> None:
        """Add result graph import to ontology graph"""
        query = f"""
            INSERT DATA {{
                GRAPH <{self.ontology_graph_iri}> {{
                    <{self.ontology_graph_iri}> <http://www.w3.org/2002/07/owl#imports>
                        <{self.output_graph_iri}>
                }}
            }}
        """
        self.client.store.sparql.update(query)

    def remove_ontology_import(self) -> None:
        """Remove ontology graph import from output graph"""
        query = f"""
            DELETE DATA {{
                GRAPH <{self.output_graph_iri}> {{
                    <{self.output_graph_iri}> <http://www.w3.org/2002/07/owl#imports>
                        <{self.ontology_graph_iri}>
                }}
            }}
        """
        self.client.store.sparql.update(query)

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
        send_result(self.client, self.output_graph_iri, Path(self.temp) / "result.nt")
        post_provenance(self)

        if self.imports or self.data_imports_ontology:
            self.add_ontology_import()
        else:
            self.remove_ontology_import()

        self.context.report.update(
            ExecutionReport(
                operation="reason",
                operation_desc="ontology and data graph processed.",
                entity_count=1,
            )
        )

    def execute(self, inputs: Sequence[Entities], context: ExecutionContext) -> None:  # noqa: ARG002
        """Execute plugin with temporary directory"""
        self.client = Client.from_context(context)
        not_exist = []
        if self.data_graph_iri not in self.client.graphs:
            not_exist.append(self.data_graph_iri)
        if self.ontology_graph_iri not in self.client.graphs:
            not_exist.append(self.ontology_graph_iri)
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
