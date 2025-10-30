"""Common constants and functions"""

import json
import shlex
from collections import OrderedDict
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from secrets import token_hex
from subprocess import CompletedProcess, run
from time import time
from xml.etree.ElementTree import Element, SubElement, tostring

from cmem.cmempy.dp.proxy.graph import get_graphs_list, post_streamed
from cmem.cmempy.dp.proxy.sparql import post as post_select
from cmem.cmempy.dp.proxy.update import post as post_update
from cmem_plugin_base.dataintegration.context import ExecutionReport
from cmem_plugin_base.dataintegration.description import PluginParameter
from cmem_plugin_base.dataintegration.parameter.choice import ChoiceParameterType
from cmem_plugin_base.dataintegration.parameter.graph import GraphParameterType
from cmem_plugin_base.dataintegration.plugins import WorkflowPlugin
from cmem_plugin_base.dataintegration.types import BoolParameterType, IntParameterType
from defusedxml import minidom

from . import __path__

ROBOT = Path(__path__[0]) / "robot.jar"

REASONERS = OrderedDict(
    {
        "elk": "ELK",
        "emr": "Expression Materializing Reasoner",
        "hermit": "HermiT",
        "jfact": "JFact",
        "structural": "Structural Reasoner",
        "whelk": "Whelk",
    }
)

MAX_RAM_PERCENTAGE_DEFAULT = 20


REASONER_PARAMETER = PluginParameter(
    param_type=ChoiceParameterType(REASONERS),
    name="reasoner",
    label="Reasoner",
    description="Reasoner option.",
)

ONTOLOGY_GRAPH_IRI_PARAMETER = PluginParameter(
    param_type=GraphParameterType(classes=["http://www.w3.org/2002/07/owl#Ontology"]),
    name="ontology_graph_iri",
    label="Ontology graph IRI",
    description="The IRI of the input ontology graph.",
)

MAX_RAM_PERCENTAGE_PARAMETER = PluginParameter(
    param_type=IntParameterType(),
    name="max_ram_percentage",
    label="Maximum RAM Percentage",
    description="""Maximum heap size for the reasoning process in the DI container. ⚠️ Setting the
    percentage too high may result in an out of memory error.""",
    default_value=MAX_RAM_PERCENTAGE_DEFAULT,
    advanced=True,
)

VALIDATE_PROFILES_PARAMETER = PluginParameter(
    param_type=BoolParameterType(),
    name="validate_profile",
    label="Validate OWL2 profiles",
    description="""Validate the input ontology against OWL profiles (DL, EL, QL, RL, and Full) and
    annotate the result graph.""",
    default_value=False,
)

IGNORE_MISSING_IMPORTS_PARAMETER = PluginParameter(
    param_type=BoolParameterType(),
    name="ignore_missing_imports",
    label="Ignore missing imports",
    description="""Ignore missing graphs from the import tree of the input graphs.""",
    default_value=False,
)


def create_xml_catalog_file(dir_: str, graphs: dict) -> None:
    """Create XML catalog file"""
    file_name = Path(dir_) / "catalog-v001.xml"
    catalog = Element("catalog")
    catalog.set("prefer", "public")
    catalog.set("xmlns", "urn:oasis:names:tc:entity:xmlns:xml:catalog")
    for i, graph in enumerate(graphs):
        uri = SubElement(catalog, "uri")
        uri.set("id", f"id{i}")
        uri.set("name", graph)
        uri.set("uri", graphs[graph])
    reparsed = minidom.parseString(tostring(catalog, "utf-8")).toxml()
    with Path(file_name).open("w", encoding="utf-8") as file:
        file.truncate(0)
        file.write(reparsed)


def send_result(iri: str | None, file: BytesIO) -> None:
    """Send result"""
    res = post_streamed(
        iri,
        file,
        replace=True,
        content_type="text/turtle",
    )
    if res.status_code != 204:  # noqa: PLR2004
        raise OSError(f"Error posting result graph (status code {res.status_code}).")


def post_provenance(plugin: WorkflowPlugin) -> None:
    """Post provenance"""
    prov = get_provenance(plugin)
    if prov:
        param_sparql = ""
        for name, iri in prov["parameters"].items():
            param_sparql += f'\n<{prov["plugin_iri"]}> <{iri}> "{plugin.__dict__[name]}" .'
        insert_query = f"""
            INSERT DATA {{
                GRAPH <{plugin.output_graph_iri}> {{
                    <{plugin.output_graph_iri}> <http://purl.org/dc/terms/creator>
                        <{prov["plugin_iri"]}> .
                    <{prov["plugin_iri"]}> a <{prov["plugin_type"]}>,
                        <https://vocab.eccenca.com/di/CustomTask> .
                    <{prov["plugin_iri"]}> <http://www.w3.org/2000/01/rdf-schema#label>
                        "{prov["plugin_label"]}" .
                    {param_sparql}
                }}
            }}
        """
        post_update(query=insert_query)


def get_provenance(plugin: WorkflowPlugin) -> dict | None:
    """Get provenance information"""
    plugin_iri = (
        f"http://dataintegration.eccenca.com/{plugin.context.task.project_id()}/"
        f"{plugin.context.task.task_id()}"
    )
    project_graph = f"http://di.eccenca.com/project/{plugin.context.task.project_id()}"

    type_query = f"""
        SELECT ?type {{
            GRAPH <{project_graph}> {{
                <{plugin_iri}> a ?type .
                FILTER(STRSTARTS(STR(?type), "https://vocab.eccenca.com/di/functions/"))
            }}
        }}
    """

    result = json.loads(post_select(query=type_query))

    try:
        plugin_type = result["results"]["bindings"][0]["type"]["value"]
    except IndexError:
        plugin.log.warning("Could not add provenance data to output graph.")
        return None

    param_split = (
        plugin_type.replace(
            "https://vocab.eccenca.com/di/functions/Plugin_",
            "https://vocab.eccenca.com/di/functions/param_",
        )
        + "_"
    )

    parameter_query = f"""
        SELECT ?parameter {{
            GRAPH <{project_graph}> {{
                <{plugin_iri}> ?parameter ?o .
                FILTER(STRSTARTS(STR(?parameter), "https://vocab.eccenca.com/di/functions/param_"))
            }}
        }}
    """

    new_plugin_iri = f"{'_'.join(plugin_iri.split('_')[:-1])}_{token_hex(8)}"
    label = f"{plugin.label} plugin"
    result = json.loads(post_select(query=parameter_query))

    prov = {
        "plugin_iri": new_plugin_iri,
        "plugin_label": label,
        "plugin_type": plugin_type,
        "parameters": {},
    }

    for binding in result["results"]["bindings"]:
        param_iri = binding["parameter"]["value"]
        param_name = param_iri.split(param_split)[1]
        prov["parameters"][param_name] = param_iri

    return prov


def robot(cmd: str, max_ram_percentage: int) -> CompletedProcess:
    """Run robot.jar"""
    cmd = f"java -XX:MaxRAMPercentage={max_ram_percentage} -jar {ROBOT} {cmd}"
    return run(shlex.split(cmd), check=False, capture_output=True)  # noqa: S603


def validate_profiles(plugin: WorkflowPlugin, graphs: dict) -> list:
    """Validate OWL2 profiles"""
    ontology_location = f"{plugin.temp}/{graphs[plugin.ontology_graph_iri]}"
    valid_profiles = []
    for profile in ("Full", "DL", "EL", "QL", "RL"):
        plugin.log.info(f"Validating {profile} profile.")
        cmd = f"merge --input {ontology_location} validate-profile --profile {profile}"
        response = robot(cmd, plugin.max_ram_percentage)
        if response.stdout.endswith(b"[Ontology and imports closure in profile]\n\n"):
            valid_profiles.append(profile)
        elif profile == "Full":
            break
    return valid_profiles


def post_profiles(plugin: WorkflowPlugin, valid_profiles: list) -> None:
    """Post OWL2 profiles"""
    if valid_profiles:
        profiles = '", "'.join(valid_profiles)
        query = f"""
            INSERT DATA {{
                GRAPH <{plugin.output_graph_iri}> {{
                    <{plugin.ontology_graph_iri}> a <http://www.w3.org/2002/07/owl#Ontology> ;
                        <https://vocab.eccenca.com/plugin/reason/profile> "{profiles}" .
                }}
            }}
        """
        post_update(query=query)


def get_output_graph_label(plugin: WorkflowPlugin, iri: str, add_string: str) -> str:
    """Create a label for the output graph"""
    graphs = (
        plugin.graphs_dict
        if hasattr(plugin, "graphs_dict")
        else {_["iri"]: _ for _ in get_graphs_list()}
    )
    try:
        data_graph_label = graphs[iri]["label"]["title"]
        data_graph_label += " - "
    except KeyError:
        data_graph_label = ""
    return f"{data_graph_label}{add_string}"


def get_file_with_datetime(plugin: WorkflowPlugin) -> BytesIO:
    """Return result file with dcterms:created datetime"""
    utctime = str(datetime.fromtimestamp(int(time()), tz=UTC))[:-6].replace(" ", "T") + "Z"
    file_content = (
        (Path(plugin.temp) / "result.ttl").read_text()
        + f"\n<{plugin.output_graph_iri}> <http://purl.org/dc/terms/created> "
        f'"{utctime}"^^xsd:dateTime .'
    ).encode("utf-8")

    return BytesIO(file_content)


def cancel_workflow(plugin: WorkflowPlugin) -> bool:
    """Cancel workflow"""
    if hasattr(plugin.context, "workflow") and plugin.context.workflow.status() != "Running":
        plugin.log.info("End task (cancelled workflow).")
        plugin.context.report.update(ExecutionReport(entity_count=0, operation_desc="(cancelled)"))
        return True
    return False
