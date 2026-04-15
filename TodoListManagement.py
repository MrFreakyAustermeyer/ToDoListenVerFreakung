"""
Example script showing how to represent todo lists and todo entries in Python
data structures and how to implement endpoint for a REST API with Flask.

Requirements:
* flask
"""

import uuid

from flask import Flask, request, jsonify, render_template


# initialize Flask server
app = Flask(__name__)


# homepage showing all lists and entries
@app.route('/')
def index():
    return render_template('index.html', todo_lists=todo_lists, todos=todos)

# create unique id for lists, entries
todo_list_1_id = '1318d3d1-d979-47e1-a225-dab1751dbe75'
todo_list_2_id = '3062dc25-6b80-4315-bb1d-a7c86b014c65'
todo_list_3_id = '44b02e00-03bc-451d-8d01-0c67ea866fee'
todo_1_id = str(uuid.uuid4())
todo_2_id = str(uuid.uuid4())
todo_3_id = str(uuid.uuid4())
todo_4_id = str(uuid.uuid4())

# define internal data structures with example data
todo_lists = [
    {'id': todo_list_1_id, 'name': 'Einkaufsliste'},
    {'id': todo_list_2_id, 'name': 'Arbeit'},
    {'id': todo_list_3_id, 'name': 'Privat'},
]
todos = [
    {'id': todo_1_id, 'name': 'Milch', 'description': '', 'list_id': todo_list_1_id},
    {'id': todo_2_id, 'name': 'Arbeitsblätter ausdrucken', 'description': '', 'list_id': todo_list_2_id},
    {'id': todo_3_id, 'name': 'Kinokarten kaufen', 'description': '', 'list_id': todo_list_3_id},
    {'id': todo_4_id, 'name': 'Eier', 'description': '', 'list_id': todo_list_1_id},
]


# helper: find a list by id
def find_list(list_id):
    for l in todo_lists:
        if l['id'] == list_id:
            return l
    return None


# helper: find an entry by id
def find_entry(entry_id):
    for e in todos:
        if e['id'] == entry_id:
            return e
    return None


# add some headers to allow cross origin access to the API on this server, necessary for using preview in Swagger Editor!
@app.after_request
def apply_cors_header(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,DELETE,PATCH'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


# define endpoint for adding a new list
@app.route('/todo-list', methods=['POST'])
def add_new_list():
    try:
        new_list = request.get_json(force=True)
    except Exception:
        return jsonify({'message': 'No valid name provided. Name must not be empty.'}), 406
    if not new_list or not new_list.get('name'):
        return jsonify({'message': 'No valid name provided. Name must not be empty.'}), 406
    new_list['id'] = str(uuid.uuid4())
    todo_lists.append(new_list)
    return jsonify(new_list), 201


# define endpoint for getting items, deleting a list, and adding entries
@app.route('/todo-list/<list_id>', methods=['GET', 'DELETE', 'POST'])
def handle_list(list_id):
    list_item = find_list(list_id)
    if not list_item:
        return jsonify({'message': f"List with id '{list_id}' not found."}), 404

    if request.method == 'GET':
        # find all todo entries for the todo list with the given id
        print('Returning todo list...')
        return jsonify([e for e in todos if e['list_id'] == list_id]), 200

    elif request.method == 'DELETE':
        # delete list with given id
        print('Deleting todo list...')
        # also remove all entries belonging to this list
        todos[:] = [e for e in todos if e['list_id'] != list_id]
        todo_lists.remove(list_item)
        return jsonify({'message': f"Todo list '{list_item['name']}' has been successfully deleted."}), 204

    elif request.method == 'POST':
        # add a new entry to this list
        try:
            new_entry = request.get_json(force=True)
        except Exception:
            return jsonify({'message': f"List with id '{list_id}' not found. No entry added."}), 404
        new_entry['id'] = str(uuid.uuid4())
        new_entry['list_id'] = list_id
        new_entry.setdefault('description', '')
        todos.append(new_entry)
        return jsonify(new_entry), 201


@app.route('/entry/<entry_id>', methods=['PATCH', 'DELETE'])
def handle_entry(entry_id):
    entry = find_entry(entry_id)
    if not entry:
        return jsonify({'message': f"Entry with id '{entry_id}' not found."}), 404

    if request.method == 'PATCH':
        try:
            data = request.get_json(force=True)
        except Exception:
            return jsonify({'message': "No valid data provided. At least 'name' or 'description' must be given."}), 406
        if not data or ('name' not in data and 'description' not in data):
            return jsonify({'message': "No valid data provided. At least 'name' or 'description' must be given."}), 406
        if 'name' in data:
            entry['name'] = data['name']
        if 'description' in data:
            entry['description'] = data['description']
        return jsonify(entry), 200

    elif request.method == 'DELETE':
        entry_name = entry['name']
        todos.remove(entry)
        return jsonify({'message': f"Entry '{entry_name}' has been successfully deleted."}), 204


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=5000)