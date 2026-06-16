"""Provider taxonomy engine.

The capability is the stable anchor; products are 0..n per capability per
provider. This package loads the canonical dataset, validates it against
``schema.json`` (schema-subset + referential integrity), and — in later phases —
discovers, triages, and trust-gates new records before they enter the dataset.
"""

__version__ = "0.1.0"
