import sqlite3
import bcrypt
import argparse

def create_user(db_path, username, email, password):
    # Hash the password using bcrypt
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Insert the new user into the users table
        cursor.execute('''
            INSERT INTO `users` 
            (`username`, `email`, `password`, `is_email_confirmed`) 
            VALUES (?, ?, ?, ?)
        ''', (username, email, hashed_password.decode('utf-8'), 1))
        
        # Commit the transaction
        conn.commit()
        print(f"User {username} created successfully.")
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        # Close the database connection
        conn.close()

def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Create a new user in the Flarum SQLite database')
    parser.add_argument('--db', default='forum_flarum_db.db', help='Path to the SQLite database')
    parser.add_argument('--username', required=True, help='Username for the new user')
    parser.add_argument('--email', required=True, help='Email for the new user')
    parser.add_argument('--password', required=True, help='Password for the new user')

    # Parse arguments
    args = parser.parse_args()

    # Create the user
    create_user(args.db, args.username, args.email, args.password)

if __name__ == '__main__':
    main()