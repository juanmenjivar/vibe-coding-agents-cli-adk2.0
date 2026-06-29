--https://codelabs.developers.google.com/getting-started-with-antigravity-skills?hl=en#4
--Level 4: Procedural Logic (database-schema-validator)

DROP TABLE IF EXISTS legacy_users;

CREATE TABLE userProfile (
    id INT PRIMARY KEY,
    bio TEXT
);

CREATE TABLE posts (
    title TEXT,
    content TEXT,
    created_at TIMESTAMP
);

CREATE TABLE comments (
    id INT PRIMARY KEY,
    post_id INT,
    body TEXT
);
