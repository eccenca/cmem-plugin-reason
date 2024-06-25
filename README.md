

# cmem-plugin-robotreason

Reasoning with ROBOT

This eccenca Corporate Memory workflow plugin performs reasoning using [ROBOT](http://robot.obolibrary.org/) (ROBOT is
an OBO Tool). It takes an OWL ontology and a data graph as inputs and writes the reasoning result to a specified graph.

[![eccenca Corporate Memory](https://img.shields.io/badge/eccenca-Corporate%20Memory-orange)](https://documentation.eccenca.com) [![workflow](https://github.com/eccenca/cmem-plugin-pyshacl/actions/workflows/check.yml/badge.svg)](https://github.com/eccenca/cmem-plugin-pyshacl/actions)  [![license](https://img.shields.io/pypi/l/cmem-plugin-pyshacl)](https://pypi.org/project/cmem-plugin-pyshacl)

## Build

:bulb: Prior to the build process, the Java library _robot.jar_ (v1.9.6) is automatically
downloaded from the [ROBOT GitHub repository](https://github.com/ontodev/robot). The file is downloaded to the directory 
_cmem_plugin_robotreason/workflow/bin_ and is not removed automatically when running `task clean`. The file can be
removed with `task custom:clean_robot`.

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

## Options

### Data graph IRI

The IRI of the input data graph. The graph IRI is selected from a list of graphs of types `di:Dataset`, `void:Dataset`
and `owl:Ontology`.

### Ontology graph IRI

The IRI of the input ontology graph. The graph IRI is selected from a list of graphs of type`owl:Ontology`.

### Result graph IRI

The IRI of the output graph for the reasoning result.

:warning: Existing graphs will be overwritten.


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
-  SubClass
- EquivalentClass
- DisjointClasses

#### Data property axiom generators
- DataPropertyCharacteristic
- EquivalentDataProperties
- SubDataProperty

#### Individual axiom generators
- ClassAssertion
- PropertyAssertion

#### Object property axiom generators
- EquivalentObjectProperty
- InverseObjectProperties
- ObjectPropertyCharacteristic
- SubObjectProperty
- ObjectPropertyRange
- ObjectPropertyDomain

