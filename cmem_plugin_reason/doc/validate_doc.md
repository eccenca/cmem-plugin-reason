A task validating the consistency of an OWL ontology (or, in unsatisfiability mode, finding
unsatisfiable classes) and generating an explanation for what was found. The plugin always
outputs entities: the explanation as text in Markdown format on the path "explanation", the
ontology IRI on the path "ontology_graph_iri", the reasoner option on the path "reasoner", and,
if OWL2 profile validation is enabled, the valid profiles on the path "profiles".

No parameter is required when the task is created, so parameters can also be set via the config
port of a workflow. The parameters are validated when the task is executed.

## Options

### Ignore missing imports

If enabled, missing imports (`owl:imports`) in the input graphs are ignored. Imports are only
read from Corporate Memory: the reasoner never fetches one from its IRI (e.g. from the web).

### Ontology graph IRI

The IRI of the input ontology graph. The graph IRI is selected from a list of graphs of type
`owl:Ontology`.

### Maximum RAM Percentage

Maximum heap size for the Java virtual machine in the DI container running the reasoning process,
as a percentage of the container's memory. The reasoning process runs next to DataIntegration's own
Java process in the same container, so both share its memory.

The reasoner holds the input graphs in memory. As a rough guide, explaining an inconsistency
in a graph with 200,000 individuals (48 MB of N-Triples) needs about 0.7 GB of heap with HermiT;
with the default of 20 %, that is a container with about 4 GB of memory. If the task fails with an out of memory error, raise the percentage or the
container's memory.

The running time depends on the ontology more than on the size of the graph. Every explanation
starts with a consistency check of the whole graph, which is slower when its individuals are
linked by properties in an ontology with existential restrictions: with the pizza ontology and
pizzas linked to their toppings, HermiT takes 0.1 s for 100 pizzas, 0.6 s for 800, 3.3 s for 4,000
and 18 s for 20,000. JFact checks 20,000 such pizzas in 4 s.

⚠️ Setting the percentage too high may result in an out of memory error of DataIntegration itself.

### Validate OWL2 profiles

Validate the input ontology against the OWL 2 profiles (Full, DL, EL, QL, RL) and annotate the
result.

An ontology graph (and each graph it imports) is only OWL 2 Full if it lacks an ontology header
(a resource of type `owl:Ontology`) or doesn't declare all its classes, properties and datatypes;
the reason is written to the task log. Other RDF-level constructs, such as statements about the
OWL vocabulary itself, are not checked: a graph that is only OWL 2 Full because of them can still
be reported as DL.

### Output graph IRI

Optional IRI of an output graph to annotate with the validation result (label, comment, and a
link back to the validated ontology). ⚠️ Existing graphs will be overwritten. Leave empty to
skip.

The output graph holds the explanation axioms plus the validation result and is declared a
`void:Dataset`. It is not declared an `owl:Ontology`: it does not contain an ontology of its
own, it describes the validated one.

### Replace blank nodes with IRIs

Advanced option, disabled by default, only relevant if an output graph is set. The explanation
axioms written to the output graph often contain class expressions (e.g. `A SubClassOf: p some B`)
or inverse properties, which are written with blank nodes. If enabled, every blank node is
replaced by an IRI, so no information is lost if the graph is processed by tools that do not keep
blank nodes.

- The IRIs are `https://<domain of the output graph>/.well-known/genid/<uuid>`, the form RDF 1.1
  recommends for replaced blank nodes; for an output graph IRI without a domain (e.g. `urn:`) they
  are `urn:uuid:<uuid>`.
- The UUIDs are computed from what the blank node stands for and from the output graph IRI, so
  re-running the task produces the same IRIs, and different output graphs never share IRIs.

### Reasoner

The following reasoner options are supported:
- [HermiT](http://www.hermit-reasoner.com/) (hermit)
- [JFact](https://github.com/owlcs/jfact) (jfact), in a version with fixes for wrong and missing
  inferences and for its speed with many individuals

Both are OWL 2 DL reasoners capable of generating explanations, which is what
consistency/unsatisfiability validation needs. HermiT is recommended: JFact lacks some reasoning
that HermiT has, so it can miss inconsistencies with keys (`HasKey`), disjoint data properties or
datatypes, and it takes `rdf:XMLLiteral` values that differ only in formatting for different
values, which can make a consistent ontology inconsistent. HermiT can take very long on some hard
ontologies and on large graphs whose individuals are linked by properties, where JFact is much
faster (see "Maximum RAM Percentage"). The advanced parameter "Timeout (minutes)" stops the task
with an error if the reasoner hasn't finished by then; by default there is no limit. Cancelling
the workflow also stops the reasoner.

### Stop at inconsistencies

Raise an error if inconsistencies are found. If enabled, the plugin does not output entities.

### Mode

Mode _inconsistency_ generates an explanation for an inconsistent ontology.
Mode _unsatisfiability_ generates explanations for many unsatisfiable classes at once. In an
inconsistent ontology every class is unsatisfiable, so this mode then fails with an error; use
mode _inconsistency_ to explain the inconsistency.

### Maximum explanations

The maximum number of independent explanations (justifications) generated per inference.
