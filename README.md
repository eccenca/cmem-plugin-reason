

# cmem-plugin-reason

This [eccenca](https://eccenca.com) [Corporate Memory](https://documentation.eccenca.com) workflow plugin bundle contains plugins performing reasoning (Reason) and ontology consistency checking (Validate) using [ROBOT](http://robot.obolibrary.org/).

[![eccenca Corporate Memory](https://img.shields.io/badge/eccenca-Corporate%20Memory-orange)](https://documentation.eccenca.com) [![workflow](https://github.com/eccenca/cmem-plugin-pyshacl/actions/workflows/check.yml/badge.svg)](https://github.com/eccenca/cmem-plugin-pyshacl/actions) [![pypi version](https://img.shields.io/pypi/v/cmem-plugin-reason)](https://pypi.org/project/cmem-plugin-reason/) [![license](https://img.shields.io/pypi/l/cmem-plugin-reason)](https://pypi.org/project/cmem-plugin-reasom)

ROBOT is published under the [BSD 3-Clause "New" or "Revised" License](https://choosealicense.com/licenses/bsd-3-clause/).
Copyright © 2015, the authors. All rights reserved.

## Build

```
➜ task clean build
```

## Installation

```
➜ cmemc admin workspace python install dist/*.tar.gz
```

Alternatively, the _build_ and _installation_ process can be initiated with the single command:

```
➜ task deploy
```

# Reason
## Options

### Data graph IRI

The IRI of the input data graph. The graph IRI is selected from a list of graphs of types `di:Dataset`, `void:Dataset`
and `owl:Ontology`.

### Ontology graph IRI

The IRI of the input ontology graph. The graph IRI is selected from a list of graphs of type`owl:Ontology`.

### Result graph IRI

The IRI of the output graph for the reasoning result.

⚠️ Existing graphs will be overwritten.

### Reasoner

The following reasoner options are supported: 
- [ELK](https://code.google.com/p/elk-reasoner/) (elk)
- [Expression Materializing Reasoner](http://static.javadoc.io/org.geneontology/expression-materializing-reasoner/0.1.3/org/geneontology/reasoner/ExpressionMaterializingReasoner.html) (emr)
- [HermiT](http://www.hermit-reasoner.com/) (hermit)
- [JFact](http://jfact.sourceforge.net/) (jfact)
- [Structural Reasoner](http://owlcs.github.io/owlapi/apidocs_4/org/semanticweb/owlapi/reasoner/structural/StructuralReasoner.html) (structural)
- [Whelk](https://github.com/balhoff/whelk) (whelk)

### Generated Axioms

By default, the reason operation will only assert inferred subclass axioms. The plugin provides the following 
parameters to include inferred axiom generators:

#### Class axiom generators
- **SubClass**  
The reasoner will infer assertions about the hierarchy of classes, i.e.
`SubClassOf:` statements.  
If there are classes `Person`, `Student` and `Professor`, such that `Person DisjointUnionOf:
Student, Professor` holds, the reasoner will infer `Student SubClassOf: Person`.  


- **EquivalentClass**  
The reasoner will infer assertions about the equivalence of classes, i.e.
`EquivalentTo:` statements.  
If there are classes `Person`, `Student` and `Professor`, such that `Person DisjointUnionOf:
Student, Professor` holds, the reasoner will infer `Person EquivalentTo: Student and Professor`.


- **DisjointClasses**  
The reasoner will infer assertions about the disjointness of classes, i.e.
`DisjointClasses:` statements.  
If there are classes `Person`, `Student` and `Professor`, such that `Person DisjointUnionOf:
Student, Professor` holds, the reasoner will infer `DisjointClasses: Student, Professor`.

  
- **EquivalentDataProperties**  
The reasoner will infer axioms about the equivalence of data properties,
 i.e. `EquivalentProperties` statements.  
If there are data properties `identifier` and `enrollmentNumber`, such that `enrollmentNumber
SubPropertyOf: identifier` and `identifier SubPropertyOf: enrollmentNumber` holds, the reasoner
will infer `Student EquivalentProperties: identifier, enrollmentNumber`.


- **SubDataProperty**  
The reasoner will infer axioms about the hierarchy of data properties,
i.e. `SubPropertyOf:` statements.  
If there are data properties `identifier`, `studentIdentifier` and `enrollmentNumber`, such that
`studentIdentifier SubPropertyOf: identifier` and `enrollmentNumber SubPropertyOf:
studentIdentifier` holds, the reasoner will infer `enrollmentNumber SubPropertyOf: identifier`.

#### Individual axiom generators
- **ClassAssertion**  
The reasoner will infer assertions about the classes of individuals, i.e.
`Types:` statements.  
Assume, there are classes `Person`, `Student` and `University` as well as the property
`enrolledIn`, such that `Student EquivalentTo: Person and enrolledIn some University` holds. For
the individual `John` with the assertions `John Types: Person; Facts: enrolledIn
LeipzigUniversity`, the reasoner will infer `John Types: Student`.


- **PropertyAssertion**  
The reasoner will infer assertions about the properties of individuals,
i.e. `Facts:` statements.  
Assume, there are properties `enrolledIn` and `offers`, such that `enrolled SubPropertyChain:
enrolledIn o inverse (offers)` holds. For the individuals `John`and `LeipzigUniversity` with the
assertions `John Facts: enrolledIn KnowledgeRepresentation` and `LeipzigUniversity Facts: offers
KnowledgeRepresentation`,  the reasoner will infer `John Facts: enrolledIn LeipzigUniversity`.

#### Object property axiom generators
- **EquivalentObjectProperty**  
The reasoner will infer assertions about the equivalence of object
properties, i.e. `EquivalentTo:` statements.  
If there are object properties `hasAlternativeLecture` and `hasSameTopicAs`, such that
`hasAlternativeLecture Characteristics: Symmetric` and `hasSameTopicAs InverseOf:
hasAlternativeLecture` holds, the reasoner will infer `EquivalentProperties: hasAlternativeLecture,
hasSameTopicAs`.


- **InverseObjectProperties**  
The reasoner will infer axioms about the inversion about object
properties, i.e. `InverseOf:` statements.  
If there is a object property `hasAlternativeLecture`, such that `hasAlternativeLecture
Characteristics: Symmetric` holds, the reasoner will infer `hasAlternativeLecture InverseOf:
hasAlternativeLecture`.


- **SubObjectProperty**  
The reasoner will infer axioms about the inclusion of object properties,
i.e. `SubPropertyOf:` statements.  
If there are object properties `enrolledIn`, `studentOf` and `hasStudent`, such that `enrolledIn
SubPropertyOf: studentOf` and `enrolledIn InverseOf: hasStudent` holds, the reasoner will infer
`hasStudent SubPropertyOf: inverse (studentOf)`.


- **ObjectPropertyRange**  
The reasoner will infer axioms about the ranges of object properties,
i.e. `Range:` statements.  
If there are classes `Student` and `Lecture` as wells as object properties `hasStudent` and
`enrolledIn`, such that `hasStudent Range: Student and enrolledIn some Lecture` holds, the
reasoner will infer `hasStudent Range: Student`.


- **ObjectPropertyDomain**  
The reasoner will infer axioms about the domains of object
properties, i.e. `Domain:` statements.  
If there are classes `Person`, `Student` and `Professor` as wells as the object property
`hasRoleIn`, such that `Professor SubClassOf: Person`, `Student SubClassOf: Person` and
`hasRoleIn Domain: Professor or Student` holds, the reasoner will infer `hasRoleIn Domain: Person`.

### Validate OWL2 profiles

Validate the input ontology against OWL profiles (DL, EL, QL, RL, and Full) and annotate the result graph. 

### Process valid OWL profiles from input

If enabled along with the "Validate OWL2 profiles" parameter, the valid profiles, ontology IRI and reasoner option is
taken from the config port input (parameters "valid_profiles", "ontology_graph_iri" and "reasoner") and the OWL2
profiles validation is not done in the plugin. The valid profiles input is a comma-separated string (e.g. "Full,DL").

### Add ontology graph import to result graph

Add the triple `<output_graph_iri> owl:imports <ontology_graph_iri>` to the output graph.

### Add result graph import to ontology graph

Add the triple `<ontology_graph_iri> owl:imports <output_graph_iri>` to the ontology graph

### Maximum RAM Percentage

Maximum heap size for the Java virtual machine in the DI container running the reasoning process.

⚠️ Setting the percentage too high may result in an out of memory error.

# Validate

The plugin outputs the explanation as text in Markdown format on the path "markdown",
the ontology IRI on the path "ontology_graph_iri", and (if enabled) the valid OWL2 profiles on the path "valid_profiles" as 
a comma-separated string.

## Options

### Ontology graph IRI

The IRI of the input ontology graph. The graph IRI is selected from a list of graphs of type`owl:Ontology`.

### Reasoner

The following reasoner options are supported: 
- [ELK](https://code.google.com/p/elk-reasoner/) (elk)
- [Expression Materializing Reasoner](http://static.javadoc.io/org.geneontology/expression-materializing-reasoner/0.1.3/org/geneontology/reasoner/ExpressionMaterializingReasoner.html) (emr)
- [HermiT](http://www.hermit-reasoner.com/) (hermit)
- [JFact](http://jfact.sourceforge.net/) (jfact)
- [Structural Reasoner](http://owlcs.github.io/owlapi/apidocs_4/org/semanticweb/owlapi/reasoner/structural/StructuralReasoner.html) (structural)
- [Whelk](https://github.com/balhoff/whelk) (whelk)

### Produce output graph

If enabled, an explanation graph is created.

### Output graph IRI

The IRI of the output graph for the reasoning result.

⚠️ Existing graphs will be overwritten.

### Write markdown explanation file

If enabled, an explanation markdown file is written to the project.

### Output filename

The filename of the Markdown file with the explanation of inconsistencies.

⚠️ Existing files will be overwritten.

### Stop at inconsistencies
Raise an error if inconsistencies are found. If enabled, the plugin does not output entities.

### Mode
Mode _inconsistency_ generates an explanation for an inconsistent ontology.  
Mode _unsatisfiability_ generates explanations for many unsatisfiable classes at once.

### Validate OWL2 profiles

Validate the input ontology against OWL profiles (DL, EL, QL, RL, and Full) and annotate the result graph.

### Output entities

Output entities. The plugin outputs the explanation as text in Markdown format on the path "markdown", the ontology IRI
on the path "ontology_graph_iri", the reasoner option on the path "reasoner", and, if enabled, the valid OWL2 profiles
on the path "valid_profiles".

### Maximum RAM Percentage

Maximum heap size for the Java virtual machine in the DI container running the reasoning process.

⚠️ Setting the percentage too high may result in an out of memory error.