"""
Database connection module for AutoBilling API.
This module provides the database connection that is used by all route modules.
"""

db = None 

def fix_mongo_id(doc):
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc 