import yaml

y = yaml.safe_load(
    """
- test: success
"""
)
print(y[0]["test"])
