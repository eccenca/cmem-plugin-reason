"""Common constants and functions"""

import re
from pathlib import Path
from subprocess import CompletedProcess, run
from xml.etree.ElementTree import Element, SubElement, tostring

import validators.url
from cmem_plugin_base.dataintegration.context import ExecutionReport
from cmem_plugin_base.dataintegration.description import PluginParameter
from cmem_plugin_base.dataintegration.parameter.graph import GraphParameterType
from cmem_plugin_base.dataintegration.plugins import WorkflowPlugin
from cmem_plugin_base.dataintegration.types import BoolParameterType, IntParameterType
from defusedxml import minidom

from . import __path__

REASONER = Path(__path__[0]) / "eccenca-reasoner.jar"

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


def cancel_workflow(plugin: WorkflowPlugin) -> bool:
    """Cancel workflow"""
    if hasattr(plugin.context, "workflow") and plugin.context.workflow.status() != "Running":
        plugin.log.info("End task (cancelled workflow).")
        plugin.context.report.update(ExecutionReport(entity_count=0, operation_desc="(cancelled)"))
        return True
    return False


def is_valid_uri(uri: str | None) -> bool:
    """Validate URI"""
    if not isinstance(uri, str):
        return False

    if uri.lower().startswith("urn:"):
        return bool(URN_PATTERN.match(uri))

    return validators.url(uri) is True
