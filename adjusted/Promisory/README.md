# Adjusted Promisory

This directory mirrors the official Promisory baseline.

All `.per` files here are required to be byte-for-byte identical to
`official/raw/Promisory/`. The module count is the frozen official baseline.

Strategy changes are not handwritten into these baseline files. Dynamic values
are exposed separately by official-derived templates under
`adjusted/cloze/Promisory/`, then rendered into test/output copies.

This keeps the original rules intact and makes every strategy change traceable
to a specific placeholder answer.
