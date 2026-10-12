# run.py
# This is the entry point to start the I-STE web server
# Run this file to start the Flask application
# Usage: python run.py

from app import create_app

# Create the Flask app using our factory function
app = create_app()

if __name__ == "__main__":
    print("="*50)
    print("  🚦 I-STE Smart Traffic System")
    print("  Starting web server...")
    print("  Open browser: http://localhost:5000")
    print("  Admin login : admin@iste.com / admin123")
    print("  User login  : rahul@example.com / user123")
    print("="*50) 

    # Start Flask development server
    # debug=True auto-reloads when you change code
    # host="0.0.0.0" allows access from phone browser
    # port=5000 is the default Flask port
    app.run(
        debug  = True,
        host   = "0.0.0.0",
        port   = 5000
    )