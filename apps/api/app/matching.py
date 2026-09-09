import re
from difflib import SequenceMatcher
from sqlalchemy import select
from .models import Supplier, Item, ItemAlias, SupplierItemMapping


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def match_supplier(db, org, name, email=None):
    suppliers = db.scalars(select(Supplier).where(Supplier.organization_id == org)).all()
    key = normalized(name)
    domain = (email or "").split("@")[-1].lower()
    matches = [s for s in suppliers if key == normalized(s.name)]
    if not matches:
        matches = [s for s in suppliers if key in map(normalized, s.aliases)]
    if not matches:
        matches = [s for s in suppliers if domain and domain == s.email_domain]
    return matches[0] if len(matches) == 1 else None


def match_item(db, org, supplier_id, sku, mpn=None, description=""):
    items = db.scalars(select(Item).where(Item.organization_id == org)).all()
    exact = [i for i in items if normalized(i.sku) == normalized(sku)]
    if len(exact) == 1:
        return exact[0], "Exact SKU", []
    exact = [i for i in items if mpn and normalized(i.manufacturer_part_number) == normalized(mpn)]
    if len(exact) == 1:
        return exact[0], "Manufacturer part", []
    mapping = db.scalar(
        select(SupplierItemMapping).where(
            SupplierItemMapping.organization_id == org,
            SupplierItemMapping.supplier_id == supplier_id,
            SupplierItemMapping.supplier_sku == sku,
        )
    )
    if mapping:
        return next((i for i in items if i.id == mapping.item_id), None), "Confirmed mapping", []
    aliases = db.scalars(select(ItemAlias).where(ItemAlias.organization_id == org)).all()
    ids = {a.item_id for a in aliases if normalized(a.alias) == normalized(sku)}
    if len(ids) == 1:
        return next(i for i in items if i.id in ids), "Known alias", []
    candidates = sorted(
        [
            {
                "id": i.id,
                "sku": i.sku,
                "description": i.description,
                "confidence": round(
                    SequenceMatcher(None, normalized(description or sku), normalized(i.description)).ratio(), 2
                ),
            }
            for i in items
        ],
        key=lambda x: x["confidence"],
        reverse=True,
    )[:3]
    # Fuzzy results are suggestions only: part substitutions require a buyer.
    return None, "Needs confirmation", candidates
