A task performing OWL reasoning. With an OWL ontology and/or a data graph as input the reasoning
result is written to a specified graph. At least one of the two input graphs must be specified. With
two different input graphs, the data graph is reasoned with the ontology imported; with only one, or
the same graph in both, that graph is reasoned on its own.

No parameter is required when the task is created, so parameters can also be set via the config
port of a workflow. The parameters are validated when the task is executed.

## Options

### Ignore missing imports

If enabled, missing imports (`owl:imports`) in the input graphs are ignored. Imports are only
read from Corporate Memory: the reasoner never fetches one from its IRI (e.g. from the web).

### Ontology graph IRI

The IRI of the input ontology graph. The graph IRI is selected from a list of graphs of type
`owl:Ontology`. Optional if a data graph is specified.

### Maximum RAM Percentage

Maximum heap size for the Java virtual machine in the DI container running the reasoning process,
as a percentage of the container's memory. The reasoning process runs next to DataIntegration's own
Java process in the same container, so both share its memory.

The reasoner holds the input graphs and its results in memory. As a rough guide, measured with
200,000 individuals (48 MB of N-Triples, 1.8 million inferred class assertions): ELK needs about
1.8 GB of heap, HermiT about 2.3 GB and JFact about 2.6 GB; with the default of 20 %, that is a
container with about 13 GB of memory. If the task fails with an out of memory error, raise the percentage or the
container's memory.

⚠️ Setting the percentage too high may result in an out of memory error of DataIntegration itself.

### Replace blank nodes with IRIs

Advanced option, disabled by default. Inferred axioms with class expressions (e.g.
`A SubClassOf: p some B`, which ELK (EMR) adds), inverse properties or disjointness of three or
more classes are written with blank nodes. If enabled, every blank node of the result is replaced
by an IRI, so no information is lost if the result is processed by tools that do not keep blank
nodes.

- The IRIs are `https://<domain of the output graph>/.well-known/genid/<uuid>`, the form RDF 1.1
  recommends for replaced blank nodes; for an output graph IRI without a domain (e.g. `urn:`) they
  are `urn:uuid:<uuid>`.
- The UUIDs are computed from what the blank node stands for and from the output graph IRI, so
  re-running the task produces the same IRIs, and different output graphs never share IRIs.

⚠️ The result is then no longer valid OWL 2 in RDF: the OWL mapping requires blank nodes for
class expressions, so tools that read the output graph as an ontology may misinterpret these
nodes.

### Reasoner

The following reasoner options are supported:
- [ELK](https://github.com/liveontologies/elk-reasoner) (elk)
- ELK wrapped in the geneontology `ExpressionMaterializingReasoner` (elk_emr), which additionally
  infers existential restrictions (`SubClassOf: R some C`) as superclasses
- [HermiT](http://www.hermit-reasoner.com/) (hermit)
- [JFact](https://github.com/owlcs/jfact) (jfact), in a version with fixes for wrong and missing
  inferences and for its speed with many individuals
- [Structural Reasoner](http://owlcs.github.io/owlapi/apidocs_4/org/semanticweb/owlapi/reasoner/structural/StructuralReasoner.html) (structural)

#### Reasoner limitations

Not every reasoner supports every axiom generator. The table shows which generators produce
inferences with which reasoner:

| Axiom generator | ELK, ELK (EMR) | HermiT | JFact | Structural |
|---|---|---|---|---|
| Class inclusion and equivalence, individual class assertions, object property inclusion | ✓ | ✓ | ✓ | partly |
| Class disjointness, individual property assertions, object property inversion, ranges and domains | **not supported** | ✓ | ✓ | partly |
| Data property equivalence and inclusion | **not supported** | ✓ | ✓ | partly |
| Same individuals, data property domains | **not supported** | ✓ | ✓ | no |
| Data and object property characteristics, object property equivalence | outside OWL 2 EL | ✓ | ✓ | partly |

- **Not supported:** ELK does not implement these inferences, so the task fails with an error
  naming the generators if one of them is selected with ELK or ELK (EMR).
- **Outside OWL 2 EL:** ELK only reasons within the OWL 2 EL profile and ignores, for example,
  functional, inverse and symmetric properties, so inferences depending on them are missed.
  Within OWL 2 EL, it also ignores keys, self restrictions, the bottom properties and clashes
  between datatype values.
- **Data values in ELK:** ELK compares the values of data property restrictions (`DataHasValue`)
  by their lexical form only, ignoring datatype and language tag: `"Paris"@en`, `"Paris"@fr` and
  `"Paris"` are the same value for it, and so are `"3"^^xsd:integer` and `"3"^^xsd:string`. With
  such restrictions it can infer wrong subclass and equivalence axioms or find a consistent
  ontology inconsistent ([ELK issue #71](https://github.com/liveontologies/elk-reasoner/issues/71));
  use HermiT or JFact for them.
- **HermiT** is complete for OWL 2 DL, but can take very long on some hard ontologies, and on large
  datasets whose individuals are linked by properties it is several times slower than JFact. The
  advanced parameter "Timeout
  (minutes)" stops the task with an error if the reasoner hasn't finished by then; by default
  there is no limit. Cancelling the workflow also stops the reasoner.
- **Structural** does no real reasoning: it only finds what follows from the asserted class and
  property hierarchies.
- **JFact** lacks some reasoning that HermiT has: keys (`HasKey`), disjoint data properties and
  parts of datatype reasoning give no inferences or inconsistencies, and `rdf:XMLLiteral` values
  that differ only in formatting are taken for different values. On some ontologies with
  nominals, its search can take very long where HermiT is fast. Prefer HermiT unless JFact is
  needed, e.g. for large datasets whose individuals are linked by properties, where JFact is
  several times faster (see below).
- **Unsatisfiable classes:** a class that can have no instances is inferred to be a subclass of
  `owl:Nothing` (with "Class inclusion"), and the task continues. Check such classes with the
  "Validate OWL consistency" task in mode _unsatisfiability_.
- **Inconsistent ontologies:** reasoning fails with an `InconsistentOntologyException` for ELK,
  HermiT and JFact (Structural produces an empty result). Check the ontology with the "Validate OWL
  consistency" task first.

#### Large datasets

Measured with 200,000 individuals of the lowest class of a chain of 10 classes (48 MB of N-Triples,
1.8 million inferred class assertions, axiom generator "Individual class assertions"):

| Reasoner | Time | Heap |
|---|---|---|
| ELK | 22 s | 1.8 GB |
| HermiT | 30 s | 2.4 GB |
| JFact | 25 s | 2.7 GB |

- How HermiT and JFact scale depends on the ontology. With individuals that only have types,
  spread over the 512 lowest classes of a tree of 1,023 classes, both grow linearly and take about
  the same time (5,000 individuals: 2 s, 40,000: 6 s). When the individuals are linked by
  properties in an ontology with existential restrictions, JFact is several times faster: with
  the pizza ontology and pizzas linked to their toppings, the task with class assertions takes
  1.0 s for 100 pizzas with HermiT, 3.1 s for 800, 14 s for 4,000 and 67 s for 20,000; JFact
  takes 1.4 s for 800, 4 s for 4,000 and 15 s for 20,000, where ELK takes 9 s; all three give the
  same result. Use ELK for large datasets if the ontology is within OWL 2
  EL, otherwise JFact, or HermiT for reasoning that JFact lacks (see above).
- ELK (EMR) creates a helper class for every class and every object property used in class or
  property axioms, so its memory grows with classes × properties: about 0.7 GB for 5,000 classes
  and 40 properties, where ELK needs 30 MB. For ontologies with many classes and properties, use
  ELK unless the existential restrictions are needed.

### Data graph IRI

The IRI of the input data graph. The graph IRI is selected from a list of graphs of types
`di:Dataset`, `void:Dataset` and `owl:Ontology`. Optional if an ontology graph is specified.

### Output graph IRI

The IRI of the output graph for the reasoning result.

⚠️ Existing graphs will be overwritten.

### Generated Axioms

The plugin provides the following parameters to include inferred axiom generators. At least one
must be enabled. **Individual class assertions** and **Individual property assertions** are
enabled by default; all others are disabled by default.

#### Class axiom generators
- **Class inclusion (rdfs:subClassOf)**
The reasoner will infer assertions about the hierarchy of classes, i.e.
`SubClassOf:` statements.
If there are classes `Person`, `Student` and `Professor`, such that `Person DisjointUnionOf:
Student, Professor` holds, the reasoner will infer `Student SubClassOf: Person`.
The Structural Reasoner only uses asserted hierarchies, so it does not infer this.

- **Class equivalence (owl:equivalentClass)**
The reasoner will infer assertions about the equivalence of named classes,
i.e. `EquivalentTo:` statements. Equivalences to class expressions are not inferred.
If there are classes `Pupil` and `Learner`, such that `Pupil SubClassOf: Learner` and `Learner
SubClassOf: Pupil` holds, the reasoner will infer `Pupil EquivalentTo: Learner`.

- **Class disjointness (owl:disjointWith)**
The reasoner will infer assertions about the disjointness of classes, i.e.
`DisjointClasses:` statements.
If there are classes `Person`, `Student` and `Professor`, such that `Person DisjointUnionOf:
Student, Professor` holds, the reasoner will infer `DisjointClasses: Student, Professor`.
**Not supported by ELK or ELK (EMR).**
The Structural Reasoner only uses asserted hierarchies, so it does not infer this.


#### Data property axiom generators
- **Data property characteristics**
The reasoner will infer characteristics of data properties, i.e.
`Characteristics:` statements. For data properties, this only pertains to functionality.
If there are data properties `identifier` and `enrollmentNumber`, such that `enrollmentNumber
SubPropertyOf: identifier` and `identifier Characteristics: Functional` holds, the reasoner will
infer `enrollmentNumber Characteristics: Functional`. ELK and ELK (EMR) ignore functional properties
(they are outside OWL 2 EL), so they do not infer this.
The Structural Reasoner only uses asserted hierarchies, so it does not infer this.

- **Data property equivalence (owl:equivalentProperty)**
The reasoner will infer axioms about the equivalence of data properties,
 i.e. `EquivalentProperties` statements.
If there are data properties `identifier` and `enrollmentNumber`, such that `enrollmentNumber
SubPropertyOf: identifier` and `identifier SubPropertyOf: enrollmentNumber` holds, the reasoner
will infer `EquivalentProperties: identifier, enrollmentNumber`.
**Not supported by ELK or ELK (EMR).**

- **Data property inclusion (rdfs:subPropertyOf)**
The reasoner will infer axioms about the hierarchy of data properties,
i.e. `SubPropertyOf:` statements.
If there are data properties `identifier`, `studentIdentifier` and `enrollmentNumber`, such that
`studentIdentifier SubPropertyOf: identifier` and `enrollmentNumber SubPropertyOf:
studentIdentifier` holds, the reasoner will infer `enrollmentNumber SubPropertyOf: identifier`.
**Not supported by ELK or ELK (EMR).**

- **Data property domains (rdfs:domain)**
The reasoner will infer axioms about the domains of data properties, i.e. `Domain:` statements.
If there are the class `Student` and the data properties `studentNumber` and `enrollmentNumber`,
such that `studentNumber Domain: Student` and `enrollmentNumber SubPropertyOf: studentNumber`
holds, the reasoner will infer `enrollmentNumber Domain: Student`.
**Not supported by ELK or ELK (EMR).**
The Structural Reasoner does not infer this.


#### Individual axiom generators
- **Individual class assertions (rdf:type)**
The reasoner will infer assertions about the classes of individuals, i.e.
`Types:` statements.
Assume, there are classes `Person`, `Student` and `University` as well as the property
`enrolledIn`, such that `Student EquivalentTo: Person and enrolledIn some University` holds. For
the individual `John` with the assertions `John Types: Person; Facts: enrolledIn
LeipzigUniversity`, the reasoner will infer `John Types: Student`.
The Structural Reasoner only uses asserted hierarchies, so it does not infer this.

- **Individual property assertions**
The reasoner will infer assertions about the properties of individuals,
i.e. `Facts:` statements.
Assume, there are properties `enrolled`, `enrolledIn` and `offers`, such that `enrolled
SubPropertyChain: enrolledIn o inverse (offers)` holds. For the individuals `John` and
`LeipzigUniversity` with the assertions `John Facts: enrolledIn KnowledgeRepresentation` and
`LeipzigUniversity Facts: offers KnowledgeRepresentation`, the reasoner will infer `John Facts:
enrolled LeipzigUniversity`.
**Not supported by ELK or ELK (EMR).**
The Structural Reasoner only uses asserted hierarchies, so it does not infer this.

- **Same individuals (owl:sameAs)**
The reasoner will infer which individuals are the same, i.e. `SameAs:` statements.
If there is the object property `hasEmail` with `hasEmail Characteristics: InverseFunctional`, and
the individuals `anna` and `annaSmith` with the assertions `anna Facts: hasEmail mail1` and
`annaSmith Facts: hasEmail mail1`, the reasoner will infer `anna SameAs: annaSmith`.
**Not supported by ELK or ELK (EMR).**
The Structural Reasoner does not infer this.


#### Object property axiom generators
- **Object property equivalence (owl:equivalentProperty)**
The reasoner will infer assertions about the equivalence of object
properties, i.e. `EquivalentTo:` statements.
If there are object properties `hasAlternativeLecture` and `hasSameTopicAs`, such that
`hasAlternativeLecture Characteristics: Symmetric` and `hasSameTopicAs InverseOf:
hasAlternativeLecture` holds, the reasoner will infer `EquivalentProperties:
hasAlternativeLecture, hasSameTopicAs`. ELK and ELK (EMR) ignore symmetric and inverse
properties (they are outside OWL 2 EL), so they do not infer this.

- **Object property inversion (owl:inverseOf)**
The reasoner will infer axioms about the inversion about object
properties, i.e. `InverseOf:` statements.
If there is a object property `hasAlternativeLecture`, such that `hasAlternativeLecture
Characteristics: Symmetric` holds, the reasoner will infer `hasAlternativeLecture InverseOf:
hasAlternativeLecture`.
**Not supported by ELK or ELK (EMR).**

- **Object property characteristics**
The reasoner will infer characteristics of object properties, i.e.
`Characteristics:` statements.
If there are object properties `enrolledIn` and `studentOf`, such that `enrolledIn
SubPropertyOf: studentOf` and `studentOf Characteristics: Functional` holds, the reasoner will
infer `enrolledIn Characteristics: Functional`. ELK and ELK (EMR) ignore functional properties
(they are outside OWL 2 EL), so they do not infer this.
The Structural Reasoner only uses asserted hierarchies, so it does not infer this.

- **Object property inclusion (rdfs:subPropertyOf)**
The reasoner will infer axioms about the inclusion of object properties,
i.e. `SubPropertyOf:` statements.
If there are object properties `enrolledIn`, `studentOf` and `hasStudent`, such that `enrolledIn
SubPropertyOf: studentOf` and `enrolledIn InverseOf: hasStudent` holds, the reasoner will infer
`hasStudent SubPropertyOf: inverse (studentOf)`. ELK and ELK (EMR) ignore inverse properties
(they are outside OWL 2 EL), so they do not infer this.

- **Object property ranges (rdfs:range)**
The reasoner will infer axioms about the ranges of object properties,
i.e. `Range:` statements.
If there are classes `Student` and `Lecture` as wells as object properties `hasStudent` and
`enrolledIn`, such that `hasStudent Range: Student and enrolledIn some Lecture` holds, the
reasoner will infer `hasStudent Range: Student`.
**Not supported by ELK or ELK (EMR).**
The Structural Reasoner only uses asserted hierarchies, so it does not infer this.

- **Object property domains (rdfs:domain)**
The reasoner will infer axioms about the domains of object
properties, i.e. `Domain:` statements.
If there are classes `Person`, `Student` and `Professor` as wells as the object property
`hasRoleIn`, such that `Professor SubClassOf: Person`, `Student SubClassOf: Person` and
`hasRoleIn Domain: Professor or Student` holds, the reasoner will infer `hasRoleIn Domain:
Person`.
**Not supported by ELK or ELK (EMR).**
The Structural Reasoner only uses asserted hierarchies, so it does not infer this.
