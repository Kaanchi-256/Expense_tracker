Spec Document
1. Overview
Replace the stub in database/db.py with a working SQLite implementation.
This step establishes the data layer foundation for the Spendly application.
All future features (authentication, profile, expense tracking) depend on this being correctly implemented.
________________________________________
2. Depends on
Nothing — this is the first step.
________________________________________
3. Routes
•	No new routes
•	Existing placeholder routes in app.py remain unchanged
________________________________________
4. Database Schema
________________________________________
A. users
Column	Type	Constraints
id	INTEGER	Primary key, autoincrement
name	TEXT	Not null
email	TEXT	Unique, not null
password_hash	TEXT	Not null
created_at	TEXT	Default datetime('now')
________________________________________
B. expenses
Column	Type	Constraints
id	INTEGER	Primary key, autoincrement
user_id	INTEGER	Foreign key → users.id, not null
amount	REAL	Not null
category	TEXT	Not null
date	TEXT	Not null (YYYY-MM-DD format)
description	TEXT	Nullable
created_at	TEXT	Default datetime('now')
________________________________________
5. Functions to Implement (database/db.py)
________________________________________
A. get_db()
•	Opens connection to spendly.db (or expense_tracker.db) in project root
•	Sets: 
o	row_factory = sqlite3.Row
o	PRAGMA foreign_keys = ON
•	Returns the connection
________________________________________
B. init_db()
•	Creates both tables using CREATE TABLE IF NOT EXISTS
•	Safe to call multiple times
•	Ensures schema is ready before app usage
________________________________________
C. seed_db()
•	Checks if users table already contains data 
o	If yes → return early (no duplication)
•	Inserts one demo user: 
o	name: Demo User
o	email: demo@spendly.com
o	password: demo123 (hashed using werkzeug)
•	Inserts 8 sample expenses: 
o	All linked to demo user
o	Cover multiple categories
o	Dates spread across current month
o	At least one expense per category
________________________________________
6. Changes to app.py
•	Import: 
o	get_db
o	init_db
o	seed_db
•	Call init_db() and seed_db() inside app.app_context() on startup
•	Ensure DB is ready before routes are used
________________________________________
7. Files to Change
•	database/db.py → implement all functions
•	app.py → add imports and startup calls
________________________________________
8. Files to Create
•	None
________________________________________
9. Dependencies
•	No new pip packages
•	Use: 
o	sqlite3 (standard library)
o	werkzeug.security (already installed)
________________________________________
10. Categories (Fixed List)
Use exactly these values:
•	Food
•	Transport
•	Bills
•	Health
•	Entertainment
•	Shopping
•	Other
________________________________________
11. Rules for Implementation
•	No ORMs (no SQLAlchemy)
•	Use parameterized queries only
•	Never use string formatting in SQL
•	Enable PRAGMA foreign_keys = ON on every connection
•	Store amount as REAL (float), not INTEGER
•	Hash passwords using:
•	fromwerkzeug.securityimportgenerate_password_hash
•	seed_db() must prevent duplicate inserts
•	Dates must follow YYYY-MM-DD format consistently
________________________________________
12. Expected Behavior
•	get_db() returns a working connection with: 
o	dictionary-like row access
o	foreign key enforcement enabled
•	init_db(): 
o	creates tables safely
o	does not fail on repeated runs
•	seed_db(): 
o	inserts demo data only once
o	does not duplicate records on multiple runs
•	Database enforces: 
o	unique email constraint
o	valid foreign key relationships
________________________________________
13. Error Handling Expectations
•	Inserting duplicate email → should fail (UNIQUE constraint)
•	Inserting expense with invalid user_id → should fail (foreign key constraint)
•	Invalid queries → should raise clear errors for debugging
________________________________________
14. Definition of Done
•	[ ] Database file is created on app startup
•	[ ] Both tables exist with correct schema and constraints
•	[ ] Demo user exists with hashed password
•	[ ] 8 sample expenses exist across categories
•	[ ] No duplicate seed data on repeated runs
•	[ ] App starts without errors
•	[ ] Foreign key enforcement works
•	[ ] All queries use parameterized SQL

