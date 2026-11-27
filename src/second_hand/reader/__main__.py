"""Entry point: ``python -m second_hand.reader`` and ``PEX_MODULE=second_hand.reader``."""

import sys

from second_hand.reader import main

if __name__ == "__main__":
    sys.exit(main())
