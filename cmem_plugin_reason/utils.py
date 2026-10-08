"""Common constants and functions for the reasoning and validation plugins.

Organized in four sections:
  1. RDF vocabulary (IRIs used in graph type filters and in the output-graph annotation).
  2. Shared across both plugins.
  3. Generic reasoner (`eccenca-reasoner.jar`, bundled with this package).
  4. N-Triples output-graph annotation.
"""

import re
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from secrets import token_hex
from subprocess import CompletedProcess, run
from urllib.parse import urlparse
from xml.etree.ElementTree import Element, SubElement, tostring

import validators.url
from cmem_client.client import Client
from cmem_client.repositories.graphs import GraphExportConfig, GraphsRepository
from cmem_client.repositories.protocols.import_item import ImportConflictPolicy
from cmem_plugin_base.dataintegration.context import ExecutionReport
from cmem_plugin_base.dataintegration.description import Plugin, PluginParameter
from cmem_plugin_base.dataintegration.parameter.graph import GraphParameterType
from cmem_plugin_base.dataintegration.plugins import WorkflowPlugin
from cmem_plugin_base.dataintegration.types import BoolParameterType, IntParameterType
from defusedxml import minidom

# ============================================================================
# 1. RDF vocabulary
# ============================================================================

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
RDFS_COMMENT = "http://www.w3.org/2000/01/rdf-schema#comment"
OWL_ONTOLOGY = "http://www.w3.org/2002/07/owl#Ontology"
OWL_IMPORTS = "http://www.w3.org/2002/07/owl#imports"
OWL_VERSION_INFO = "http://www.w3.org/2002/07/owl#versionInfo"
#: The build of the bundled reasoner jar that produced an output graph, recorded in the provenance
REASONER_VERSION = "https://vocab.eccenca.com/plugin/reason/reasonerVersion"
REASONER_COMMIT = "https://vocab.eccenca.com/plugin/reason/reasonerCommit"
DCTERMS_SOURCE = "http://purl.org/dc/terms/source"
DCTERMS_CREATED = "http://purl.org/dc/terms/created"
DI_DATASET = "https://vocab.eccenca.com/di/Dataset"
VOID_DATASET = "http://rdfs.org/ns/void#Dataset"
XSD_DATETIME = "http://www.w3.org/2001/XMLSchema#dateTime"
DI_FUNCTIONS = "https://vocab.eccenca.com/di/functions/"
DI_TASKS = "http://dataintegration.eccenca.com/"

#: Distribution name of this plugin, for its version in the provenance data
PACKAGE_NAME = "cmem-plugin-reason"


# ============================================================================
# 2. Shared
# ============================================================================

MAX_RAM_PERCENTAGE_DEFAULT = 20
URN_PATTERN = re.compile(r"^urn:[a-zA-Z0-9][a-zA-Z0-9-]*(:.+)?$", re.IGNORECASE)

ONTOLOGY_GRAPH_IRI_PARAMETER = PluginParameter(
    param_type=GraphParameterType(classes=[OWL_ONTOLOGY]),
    name="ontology_graph_iri",
    label="Ontology graph IRI",
    description="The IRI of the input ontology graph.",
    # no parameter is required at creation (they may be set via the config port); the plugins
    # validate them at execution
    default_value="",
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
    """Get provenance information for the running plugin task, as a snapshot of the task.

    Everything is derived from the plugin's registration and the execution context, not read
    from the project graph: that graph only exists if the workspace is stored as RDF
    (workspace provider "backend" or "fileAndDataPlatform").
    """
    task = getattr(plugin.context, "task", None)
    description = next((d for d in Plugin.plugins if d.plugin_class is type(plugin)), None)
    if task is None or description is None:
        plugin.log.warning("Could not add provenance data to output graph.")
        return None

    # The same IRIs DataIntegration uses for the task type and its parameters in the project graph
    plugin_type = f"{DI_FUNCTIONS}Plugin_{description.plugin_id}"
    param_prefix = f"{DI_FUNCTIONS}param_{description.plugin_id}_"
    # A snapshot of the task: replace the random suffix of the task ID, so that the provenance
    # does not merge with the live task
    task_name = task.task_id().rsplit("_", 1)[0]
    plugin_iri = f"{DI_TASKS}{task.project_id()}/{task_name}_{token_hex(8)}"

    return {
        "plugin_iri": plugin_iri,
        "plugin_label": f"{plugin.label} plugin",
        "plugin_type": plugin_type,
        "plugin_version": get_plugin_version(),
        "reasoner_version": get_reasoner_version(plugin.max_ram_percentage),
        "parameters": {p.name: f"{param_prefix}{p.name}" for p in description.parameters},
    }


def get_plugin_version() -> str | None:
    """Get the installed version of this plugin package (None if it is not installed)"""
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return None


def post_provenance(plugin: WorkflowPlugin) -> None:
    """Write provenance (creator task IRI + parameter values) into the output graph"""
    prov = get_provenance(plugin)
    if prov:
        param_sparql = ""
        for name, iri in prov["parameters"].items():
            # only record parameters that are exposed as plugin attributes
            if name in plugin.__dict__:
                param_sparql += f'\n<{prov["plugin_iri"]}> <{iri}> "{plugin.__dict__[name]}" .'
        version_sparql = (
            f'<{prov["plugin_iri"]}> <{OWL_VERSION_INFO}> "{prov["plugin_version"]}" .'
            if prov["plugin_version"]
            else ""
        )
        if prov["reasoner_version"]:
            reasoner_version, reasoner_commit = prov["reasoner_version"]
            version_sparql += (
                f'\n<{prov["plugin_iri"]}> <{REASONER_VERSION}> "{reasoner_version}" .'
                f'\n<{prov["plugin_iri"]}> <{REASONER_COMMIT}> "{reasoner_commit}" .'
            )
        insert_query = f"""
            INSERT DATA {{
                GRAPH <{plugin.output_graph_iri}> {{
                    <{plugin.output_graph_iri}> <http://purl.org/dc/terms/creator>
                        <{prov["plugin_iri"]}> .
                    <{prov["plugin_iri"]}> a <{prov["plugin_type"]}>,
                        <https://vocab.eccenca.com/di/CustomTask> .
                    <{prov["plugin_iri"]}> <http://www.w3.org/2000/01/rdf-schema#label>
                        "{prov["plugin_label"]}" .
                    {version_sparql}
                    {param_sparql}
                }}
            }}
        """
        plugin.client.store.sparql.update(insert_query)


# ============================================================================
# 3. Generic reasoner (eccenca-reasoner.jar, bundled)
# ============================================================================

REASONER = str(Path(__file__).parent / "eccenca-reasoner.jar")

#: Name of the XML catalog file written by create_xml_catalog_file() and passed to the
#: reasoner via --catalog, so that owl:imports are resolved to the locally fetched graphs.
CATALOG_FILENAME = "catalog-v001.xml"

#: Name of the N-Triples file the reasoner writes via --output. The plugins append their
#: annotation triples to it before uploading it as the output graph.
RESULT_FILENAME = "result.nt"


def create_xml_catalog_file(dir_: str, graphs: dict) -> None:
    """Create XML catalog file"""
    file_name = Path(dir_) / CATALOG_FILENAME
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


def skolem_base(graph_iri: str) -> str:
    """IRI prefix for the reasoner's --skolem-base, derived from the output graph IRI.

    For an http(s) graph IRI this is the RDF 1.1 well-known path for skolem IRIs at the root of
    its domain (https://example.org/.well-known/genid/), so consumers can recognize them as
    replaced blank nodes. Other IRIs (e.g. urn:) have no domain; they get urn:uuid: IRIs.
    """
    parsed = urlparse(graph_iri)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}/.well-known/genid/"
    return "urn:uuid:"


def skolem_args(output_graph_iri: str) -> list[str]:
    """Reasoner arguments that replace the blank nodes of --output with IRIs.

    The output graph IRI is the scope, so different output graphs never share IRIs.
    """
    return [
        "--skolemize",
        "--skolem-base",
        skolem_base(output_graph_iri),
        "--skolem-scope",
        output_graph_iri,
    ]


#: Output of `java -jar eccenca-reasoner.jar --version`
REASONER_VERSION_LINE = re.compile(
    r"^eccenca-reasoner (?P<version>\S+) \(commit (?P<commit>\S+)\)$"
)


def get_reasoner_version(max_ram_percentage: int) -> tuple[str, str] | None:
    """Get version and commit of the bundled reasoner jar.

    None if the jar can't report them: jars built before the --version option reject it, and
    jars built without git information report "unknown".
    """
    response = eccenca_reasoner(["--version"], max_ram_percentage)
    match = REASONER_VERSION_LINE.match(response.stdout.decode().strip())
    if response.returncode != 0 or match is None or "unknown" in match.groups():
        return None
    return match["version"], match["commit"]


def eccenca_reasoner(cmd: list[str], max_ram_percentage: int) -> CompletedProcess[bytes]:
    """Run eccenca_reasoner.jar"""
    full_cmd = ["java", f"-XX:MaxRAMPercentage={max_ram_percentage}", "-jar", REASONER, *cmd]
    return run(full_cmd, check=False, capture_output=True)  # noqa: S603


# ============================================================================
# 4. N-Triples output-graph annotation
# ============================================================================


def escape_nt_literal(text: str) -> str:
    """Escape a string for use in an N-Triples literal (backslash, quote, control chars)."""
    return (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def build_annotation_nt(
    graph_iri: str,
    label: str,
    comment: str,
    sources: list[str],
    rdf_type: str,
) -> str:
    """Build the N-Triples annotation both plugins prepend to their output graph.

    Declares `graph_iri` as an instance of `rdf_type`, gives it a human-readable rdfs:label
    and rdfs:comment, links it back to each input graph via dcterms:source, and records a
    dcterms:created timestamp (pass `utc_now_xsd()` unless a fixed value is needed).
    Pass OWL_ONTOLOGY for an output graph that is itself an OWL ontology (the reasoning result),
    VOID_DATASET for a graph that merely reports on an input graph (the validation result).
    Written as plain N-Triples lines (full IRIs, no prefixes) rather than via an RDF
    library, so `label` and `comment` are escaped by hand; the IRIs are not escaped.
    """
    utc_now_xsd = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        f"<{graph_iri}> <{RDF_TYPE}> <{rdf_type}> .",
        f'<{graph_iri}> <{RDFS_LABEL}> "{escape_nt_literal(label)}"@en .',
        f'<{graph_iri}> <{RDFS_COMMENT}> "{comment}"@en .',
        f'<{graph_iri}> <{DCTERMS_CREATED}> "{utc_now_xsd}"^^<{XSD_DATETIME}> .',
    ]
    lines += [f"<{graph_iri}> <{DCTERMS_SOURCE}> <{source}> ." for source in sources]
    return "\n".join(lines) + "\n"
