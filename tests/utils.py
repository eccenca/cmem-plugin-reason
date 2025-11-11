"""Common functions"""

from io import BytesIO
from pathlib import Path

from cmem.cmempy.dp.proxy.graph import get, post_streamed
from rdflib import DCTERMS, OWL, RDF, Graph, URIRef

UID = "e02aaed014c94e0c91bf960fed127750"

FIXTURE_DIR = Path(__file__).parent / "fixture_dir"


def get_remote_graph(iri: str) -> Graph:
    """Get remote graph IRI"""
    graph = Graph().parse(
        data=get(iri, owl_imports_resolution=False).text,
        format="turtle",
    )
    graph.remove((URIRef(iri), DCTERMS.created, None))
    graph.remove((None, RDF.type, OWL.AnnotationProperty))
    return graph


def import_graph(iri: str, file: BytesIO) -> None:
    """Import graph to CMEM"""
    res = post_streamed(iri, file, replace=True)
    if res.status_code != 204:  # noqa: PLR2004
        raise ValueError(f"Response {res.status_code}: {res.url}")


def replace_uuid(filepath: str) -> str:
    """Replace {uuid} in input files"""
    return Path(filepath).read_text().replace("{uuid}", UID)


def get_bytes_io(filepath: str) -> BytesIO:
    """Get BytesIO object from filepath"""
    return BytesIO(replace_uuid(filepath).encode(encoding="utf-8"))
