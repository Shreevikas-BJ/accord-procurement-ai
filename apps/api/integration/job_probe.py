"""Explicit fault injection used only by the opt-in Docker verification suite."""

import time


def timeout_document_job(document_id, organization_id):
    time.sleep(5)
