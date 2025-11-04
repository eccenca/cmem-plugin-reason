

from pathlib import Path
from subprocess import CompletedProcess, run
import shlex


ROBOT = Path("cmem_plugin_reason") / "robot.jar"


def robot(cmd: str, max_ram_percentage: int) -> CompletedProcess:
    """Run robot.jar"""
    print("run")
    cmd = f"java -XX:MaxRAMPercentage={max_ram_percentage} -jar {ROBOT} {cmd}"
    print(cmd)
    return run(shlex.split(cmd), check=False, capture_output=True)  # noqa: S603

data_location = "test_temp/13e394ba16354b219bf68528d3dcc2f1.nt"
cmd = (
            f'reason --input "{data_location}" '
            # f"--reasoner elk "
            # f'--axiom-generators "{axioms}" '
            # f"--include-indirect true "
            # f"--exclude-duplicate-axioms true "
            # f"--exclude-owl-thing true "
            # f"--exclude-tautologies all "
            # f"--exclude-external-entities "
            # f"reduce --reasoner {self.reasoner} "
            # f'unmerge --input "{data_location}" '
            # f'annotate --ontology-iri "{self.output_graph_iri}" '
            # f"--remove-annotations "
            # f'--language-annotation rdfs:label "{label}" en '
            # f"--language-annotation rdfs:comment "
            # f'"Reasoning results of data graph <{self.data_graph_iri}> with ontology '
            # f'<{self.ontology_graph_iri}>" en '
            # f'--link-annotation dc:source "{self.data_graph_iri}" '
            # f'--link-annotation dc:source "{self.ontology_graph_iri}" '
            f'--output "test_result.ttl"'
)

robot(cmd, 10)