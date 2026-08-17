"""Common functions"""

from pathlib import Path
from tempfile import TemporaryDirectory

from cmem_client.client import Client
from cmem_client.repositories.graphs import GraphExportConfig, GraphsRepository
from cmem_client.repositories.protocols.import_item import ImportConflictPolicy
from cmem_plugin_base.dataintegration.client import get_client
from cmem_plugin_base.testing import TestPluginContext
from rdflib import DCTERMS, OWL, RDF, Graph, URIRef

UID = "e02aaed014c94e0c91bf960fed127750"

FIXTURE_DIR = Path(__file__).parent / "fixture_dir"

TTL_EXPORT_CONFIG = GraphExportConfig(serialization=GraphsRepository.formats["turtle"])


def get_test_client() -> Client:
    """Get a cmem-client for the test user

    A new client with a new context is returned on every call: TestUserContext requests
    its access token once on creation and never refreshes it, and the client's
    repositories cache the remote state on first access, while the plugins under test
    change that state with their own client.
    """
    return get_client(TestPluginContext())


def get_remote_graph(client: Client, iri: str) -> Graph:
    """Get remote graph IRI"""
    with TemporaryDirectory() as temp:
        path = Path(temp) / "graph.ttl"
        client.graphs.export_item(key=iri, path=path, configuration=TTL_EXPORT_CONFIG)
        graph = Graph().parse(source=path, format="turtle")
    graph.remove((URIRef(iri), DCTERMS.created, None))
    graph.remove((None, RDF.type, OWL.AnnotationProperty))
    return graph


def import_graph(client: Client, iri: str, filepath: str) -> None:
    """Import graph to CMEM"""
    with TemporaryDirectory() as temp:
        path = Path(temp) / Path(filepath).name
        path.write_text(replace_uuid(filepath), encoding="utf-8")
        client.graphs.import_item(path=path, key=iri, on_conflict=ImportConflictPolicy.REPLACE)


def replace_uuid(filepath: str) -> str:
    """Replace {uuid} in input files"""
    return Path(filepath).read_text().replace("{uuid}", UID)
