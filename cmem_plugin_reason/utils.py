"""Common constants and functions for the reasoning and validation plugins.

Organized in two sections:
  1. Shared across both plugins.
  2. Generic reasoner (`eccenca-reasoner.jar`, bundled with this package).
"""

import re
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex
from subprocess import CompletedProcess, run
from time import time
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring

import validators.url
from cmem_client.client import Client
from cmem_client.repositories.graphs import GraphExportConfig, GraphsRepository
from cmem_client.repositories.protocols.import_item import ImportConflictPolicy
from cmem_plugin_base.dataintegration.context import ExecutionReport
from cmem_plugin_base.dataintegration.description import PluginParameter
from cmem_plugin_base.dataintegration.parameter.graph import GraphParameterType
from cmem_plugin_base.dataintegration.plugins import WorkflowPlugin
from cmem_plugin_base.dataintegration.types import BoolParameterType, IntParameterType
from defusedxml import minidom

from . import __path__

# ============================================================================
# 1. Shared
# ============================================================================

MAX_RAM_PERCENTAGE_DEFAULT = 20
URN_PATTERN = re.compile(r"^urn:[a-zA-Z0-9][a-zA-Z0-9-]*(:.+)?$", re.IGNORECASE)

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

IGNORE_MISSING_IMPORTS_PARAMETER = PluginParameter(
    param_type=BoolParameterType(),
    name="ignore_missing_imports",
    label="Ignore missing imports",
    description="""Ignore missing graphs from the import tree of the input graphs.""",
    default_value=False,
)

VALIDATE_PROFILES_PARAMETER = PluginParameter(
    param_type=BoolParameterType(),
    name="validate_profile",
    label="Validate OWL2 profiles",
    description="""Validate the input ontology against the OWL 2 profiles (Full, DL, EL, QL, RL)
    and annotate the result.""",
    default_value=False,
)


def is_valid_uri(uri: str | None) -> bool:
    """Validate a URI (http(s) URL or urn:)"""
    if not isinstance(uri, str):
        return False
    if uri.lower().startswith("urn:"):
        return bool(URN_PATTERN.match(uri))
    return validators.url(uri) is True


def cancel_workflow(plugin: WorkflowPlugin) -> bool:
    """Return True (and report) if the surrounding workflow was cancelled"""
    if hasattr(plugin.context, "workflow") and plugin.context.workflow.status() != "Running":
        plugin.log.info("End task (cancelled workflow).")
        plugin.context.report.update(ExecutionReport(entity_count=0, operation_desc="(cancelled)"))
        return True
    return False


def raise_on_error(response: CompletedProcess, context: str = "Reasoner") -> None:
    """Raise an OSError carrying the engine output if the process failed"""
    if response.returncode != 0:
        if response.stderr:
            raise OSError(f"{context} error: {response.stderr.decode().strip()}")
        if response.stdout:
            raise OSError(f"{context} error: {response.stdout.decode().strip()}")
        raise OSError(f"{context} error (exit code {response.returncode}).")


def get_graph_as_file(client: Client, iri: str, path: Path) -> Path:
    """Fetch a graph from CMEM and store it locally as N-Triples (owl:imports not resolved)"""
    exported_path: Path = client.graphs.export_item(
        key=iri,
        path=path,
        replace=True,
        configuration=GraphExportConfig(serialization=GraphsRepository.formats["n-triples"]),
    )
    return exported_path


def send_result(client: Client, iri: str | None, path: Path) -> None:
    """Send result graph file to CMEM (replace)"""
    client.graphs.import_item(path=path, key=iri, on_conflict=ImportConflictPolicy.REPLACE)


def get_file_with_datetime(plugin: WorkflowPlugin, filename: str = "result.ttl") -> Path:
    """Append a dcterms:created datetime to the result file (in place) and return its path"""
    utctime = str(datetime.fromtimestamp(int(time()), tz=UTC))[:-6].replace(" ", "T") + "Z"
    path = Path(plugin.temp) / filename
    with path.open("a", encoding="utf-8") as file:
        file.write(
            f"\n<{plugin.output_graph_iri}> <http://purl.org/dc/terms/created> "
            f'"{utctime}"^^<http://www.w3.org/2001/XMLSchema#dateTime> .'
        )
    return path


def get_output_graph_label(plugin: WorkflowPlugin, iri: str, add_string: str) -> str:
    """Create a label for the output graph based on a source graph label"""
    if hasattr(plugin, "graphs_dict"):
        graphs = plugin.graphs_dict
    elif hasattr(plugin, "client"):
        graphs = plugin.client.graphs
    else:
        # plugin.client is only set inside execute(); support being called standalone too
        graphs = Client.from_env().graphs
    graph = graphs.get(iri)
    data_graph_label = f"{graph.label.title} - " if graph is not None and graph.label else ""
    return f"{data_graph_label}{add_string}"


def get_provenance(plugin: WorkflowPlugin) -> dict | None:
    """Get provenance information for the running plugin task"""
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
    result = list(plugin.client.store.sparql.query(type_query))
    if not result:
        plugin.log.warning("Could not add provenance data to output graph.")
        return None
    plugin_type = str(result[0].type)  # type: ignore[union-attr]

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
    result = list(plugin.client.store.sparql.query(parameter_query))

    prov: dict[str, Any] = {
        "plugin_iri": new_plugin_iri,
        "plugin_label": label,
        "plugin_type": plugin_type,
        "parameters": {},
    }
    for row in result:
        param_iri = str(row.parameter)  # type: ignore[union-attr]
        param_name = param_iri.split(param_split)[1]
        prov["parameters"][param_name] = param_iri
    return prov


def post_provenance(plugin: WorkflowPlugin) -> None:
    """Write provenance (creator task IRI + parameter values) into the output graph"""
    prov = get_provenance(plugin)
    if prov:
        param_sparql = ""
        for name, iri in prov["parameters"].items():
            # only record parameters that are exposed as plugin attributes
            if name in plugin.__dict__:
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
        plugin.client.store.sparql.update(insert_query)


# ============================================================================
# 2. Generic reasoner (eccenca-reasoner.jar, bundled)
# ============================================================================

REASONER = Path(__path__[0]) / "eccenca-reasoner.jar"


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


def eccenca_reasoner(cmd: list[str], max_ram_percentage: int) -> CompletedProcess[bytes]:
    """Run eccenca_reasoner.jar"""
    full_cmd = ["java", f"-XX:MaxRAMPercentage={max_ram_percentage}", "-jar", str(REASONER), *cmd]
    return run(full_cmd, check=False, capture_output=True)  # noqa: S603
