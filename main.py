import os
import sqlite3
import pandas as pd
import glob
import tempfile
import shutil
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'sqlviewer_secret_key'

# Configuration
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload

# Database file path
db_file_path = None

def get_connection():
    if db_file_path and os.path.exists(db_file_path):
        try:
            conn = sqlite3.connect(db_file_path)
            return conn
        except sqlite3.Error as e:
            flash(f"Database connection error: {str(e)}", "error")
            return None
    return None

def get_tables(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return tables

def get_table_columns(conn, table_name):
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info('{table_name}')")
        columns = []
        for row in cursor.fetchall():
            # cid, name, type, notnull, dflt_value, pk
            columns.append((
                row[1],  # name
                row[2],  # type
                'NOT NULL' if row[3] else '',  # null
                'PK' if row[5] else '',  # key
                row[4] or '',  # default
                ''  # extra
            ))
        cursor.close()
        return columns
    except Exception as e:
        flash(f"Error getting table columns: {str(e)}", "error")
        return []

def get_table_stats(conn, table_name, filters=None):
    try:
        # Prepare WHERE clause for filtering
        where_clause = ""
        params = []
        
        if filters:
            conditions = []
            for f in filters:
                column = f['column']
                operator = f['operator']
                value = f['value']
                
                if operator == 'IN':
                    # Handle IN operator with comma-separated values
                    in_values = value.split(',')
                    placeholders = ','.join(['?' for _ in in_values])
                    conditions.append(f"[{column}] IN ({placeholders})")
                    params.extend(in_values)
                elif operator == 'LIKE':
                    conditions.append(f"[{column}] LIKE ?")
                    params.append(value)
                else:
                    conditions.append(f"[{column}] {operator} ?")
                    params.append(value)
            
            if conditions:
                where_clause = " WHERE " + " AND ".join(conditions)
        
        # Get total row count (unfiltered)
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM '{table_name}'")
        total_unfiltered_count = cursor.fetchone()[0]
        
        # Get filtered row count if filters are applied
        if filters and where_clause:
            count_query = f"SELECT COUNT(*) FROM '{table_name}'{where_clause}"
            cursor.execute(count_query, params)
            filtered_count = cursor.fetchone()[0]
        else:
            filtered_count = total_unfiltered_count
        
        # Determine if we should show all data or a sample
        show_all_data = filtered_count <= 1000 and filters
        
        # Query for data analysis
        if filters and where_clause:
            if show_all_data:
                # Get all filtered data for small result sets
                query = f"SELECT * FROM '{table_name}'{where_clause}"
                df = pd.read_sql_query(query, conn, params=params)
            else:
                # Get a random sample of the filtered data for large result sets
                query = f"SELECT * FROM '{table_name}'{where_clause} ORDER BY RANDOM() LIMIT 1000"
                df = pd.read_sql_query(query, conn, params=params)
        else:
            # No filters, use random sampling
            query = f"SELECT * FROM '{table_name}' ORDER BY RANDOM() LIMIT 1000"
            df = pd.read_sql_query(query, conn)
        
        # Determine how many rows to display in the sample
        if show_all_data:
            sample_display = df.to_html(classes='table table-striped table-hover', index=False, border=0)
        else:
            sample_display = df.head(10).to_html(classes='table table-striped table-hover', index=False, border=0)
        
        stats = {
            'row_count': len(df) if show_all_data else filtered_count,
            'sample': sample_display,
            'column_stats': {},
            'total_row_count': total_unfiltered_count
        }
        
        # Get column statistics
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                stats['column_stats'][col] = {
                    'min': df[col].min(),
                    'max': df[col].max(),
                    'mean': df[col].mean(),
                    'median': df[col].median(),
                    'null_count': df[col].isna().sum()
                }
            else:
                stats['column_stats'][col] = {
                    'unique_values': df[col].nunique(),
                    'most_common': df[col].value_counts().head(3).to_dict(),
                    'null_count': df[col].isna().sum()
                }
        
        cursor.close()
        return stats, show_all_data
    except Exception as e:
        flash(f"Error getting stats: {str(e)}", "error")
        return None, False

def find_db_file(filename):
    """
    Search for database files with the given filename in common locations
    """
    # Try to find the database file in standard locations
    search_paths = [
        os.path.join(os.getcwd(), filename),  # Current directory
        os.path.join(os.path.expanduser("~"), filename),  # User's home directory
        os.path.join(os.path.expanduser("~"), "Downloads", filename),  # Downloads folder
        os.path.join(os.path.expanduser("~"), "Documents", filename),  # Documents folder
        filename  # Absolute path
    ]
    
    # Drive letters to search (Windows)
    if os.name == 'nt':
        import string
        drives = [f'{d}:' for d in string.ascii_uppercase if os.path.exists(f'{d}:')]
        for drive in drives:
            search_paths.append(os.path.join(drive, filename))
    
    # Check each path
    for path in search_paths:
        if os.path.exists(path) and os.path.isfile(path):
            return path
    
    # If not found in standard locations, try to find it with glob
    for ext in ['.db', '.sqlite', '.sqlite3']:
        # Search in current directory and subdirectories
        for file in glob.glob(f"**/*{filename}*{ext}", recursive=True):
            if os.path.isfile(file):
                return os.path.abspath(file)
    
    return None

@app.route('/')
def index():
    global db_file_path
    conn = get_connection()
    tables = []
    
    if conn:
        tables = get_tables(conn)
        conn.close()
        return render_template('index.html', tables=tables, connected=True, db_file=db_file_path)
    else:
        db_file_path = None
        return render_template('index.html', connected=False)

@app.route('/connect', methods=['POST'])
def connect_to_db():
    global db_file_path
    
    # Check if a file was uploaded
    if 'db_file' in request.files and request.files['db_file'].filename:
        file = request.files['db_file']
        filename = secure_filename(file.filename)
        
        # Save the uploaded file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Set the database file path to the uploaded file
        db_file_path = file_path
        
        # Test connection
        conn = get_connection()
        if conn:
            flash(f"Successfully connected to uploaded database: {filename}", "success")
            conn.close()
        else:
            flash("Failed to open uploaded database. Please check if it's a valid SQLite database file.", "error")
            # Remove the invalid file
            if os.path.exists(file_path):
                os.remove(file_path)
            db_file_path = None
    
    # If no file was uploaded, check for a path
    elif request.form.get('db_path'):
        local_path = request.form.get('db_path')
        
        # If it looks like just a filename (from the file browser), try to find the full path
        if not os.path.isabs(local_path) and not local_path.startswith('./') and not local_path.startswith('../'):
            found_path = find_db_file(local_path)
            if found_path:
                local_path = found_path
        
        # Normalize path and check if file exists
        local_path = os.path.abspath(os.path.expanduser(local_path))
        
        if not os.path.exists(local_path):
            flash(f"Database file not found: {local_path}", "error")
            return redirect(url_for('index'))
        
        # Set the database file path
        db_file_path = local_path
        
        # Test connection
        conn = get_connection()
        if conn:
            flash(f"Successfully connected to database: {local_path}", "success")
            conn.close()
        else:
            flash("Failed to open database. Please check if it's a valid SQLite database file.", "error")
            db_file_path = None
    
    else:
        flash("Please provide a database file or path", "error")
    
    return redirect(url_for('index'))

@app.route('/view_table/<table_name>')
def view_table(table_name):
    conn = get_connection()
    if conn:
        columns = get_table_columns(conn, table_name)
        stats, all_data = get_table_stats(conn, table_name)
        conn.close()
        return render_template('table_view.html', 
                              table_name=table_name, 
                              columns=columns, 
                              stats=stats,
                              is_filtered=False,
                              all_data=all_data)
    else:
        flash("Connection failed. Please check your database file.", "error")
        return redirect(url_for('index'))

@app.route('/filter_table/<table_name>', methods=['POST'])
def filter_table(table_name):
    conn = get_connection()
    if conn:
        # Get columns info
        columns = get_table_columns(conn, table_name)
        
        # Get filter parameters
        filter_columns = request.form.getlist('column[]')
        filter_operators = request.form.getlist('operator[]')
        filter_values = request.form.getlist('value[]')
        
        # Create filter conditions
        filters = []
        for i in range(len(filter_columns)):
            if filter_columns[i] and filter_operators[i] and filter_values[i]:
                filters.append({
                    'column': filter_columns[i],
                    'operator': filter_operators[i],
                    'value': filter_values[i]
                })
        
        # Get filtered stats
        stats, all_data = get_table_stats(conn, table_name, filters)
        conn.close()
        
        if not stats:
            flash("Error applying filters.", "error")
            return redirect(url_for('view_table', table_name=table_name))
        
        return render_template('table_view.html',
                              table_name=table_name,
                              columns=columns,
                              stats=stats,
                              is_filtered=True,
                              all_data=all_data)
    else:
        flash("Connection failed. Please check your database file.", "error")
        return redirect(url_for('index'))

@app.route('/disconnect')
def disconnect():
    global db_file_path
    
    # If it's an uploaded file in our uploads directory, delete it
    if db_file_path and os.path.exists(db_file_path) and db_file_path.startswith(os.path.abspath(UPLOAD_FOLDER)):
        try:
            os.remove(db_file_path)
            flash(f"Uploaded database file removed.", "info")
        except Exception as e:
            flash(f"Error removing file: {str(e)}", "error")
    
    db_file_path = None
    flash("Disconnected from the database.", "info")
    return redirect(url_for('index'))

def main():
    print("Starting SQL Viewer on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)

if __name__ == "__main__":
    main()
