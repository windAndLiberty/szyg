"""Shared manifest for the expert marketplace runtime resources."""

RESOURCE_DIRNAME = "agency_agents"

# Ordered by business priority: acquisition, operations, then support roles.
RETAINED_DIVISIONS = (
    "marketing",
    "paid-media",
    "sales",
    "specialized",
    "product",
    "project-management",
    "support",
    "academic",
    "design",
    "finance",
    "gis",
)

EXCLUDED_DIVISIONS = (
    "engineering",
    "game-development",
    "security",
    "spatial-computing",
    "testing",
)
