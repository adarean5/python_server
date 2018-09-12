"""An example of a simple HTTP server."""
from __future__ import print_function

import mimetypes
import pickle
import socket
from os.path import isdir

try:
    from urllib.parse import unquote_plus
except ImportError:
    from urllib import unquote_plus

# Pickle file for storing data
PICKLE_DB = "db.pkl"

# Directory containing www data
WWW_DATA = "www-data"

# Header template for a successful HTTP request
HEADER_RESPONSE_200 = """HTTP/1.1 200 OK
content-type: %s
content-length: %d
connection: Close

"""

# Represents a table row that holds user data
TABLE_ROW = """
<tr>
    <td>%d</td>
    <td>%s</td>
    <td>%s</td>
</tr>
"""

# Template for a 404 (Not found) error
RESPONSE_404 = """HTTP/1.1 404 Not found
content-type: text/html
connection: Close

<!doctype html>
<h1>404 Page not found</h1>
<p>Page cannot be found.</p>
"""

# 400
RESPONSE_400 = """HTTP/1.1 400 Bad Request
content-type: text/html
connection: Close

<!doctype html>
<h1>400 Bad request</h1>
<p>Your browser sent a request that this server could not understand.</p>
<p>The request line contained invalid characters following the protocol string.</p>
"""

# 301
RESPONSE_301 = """HTTP/1.1 301 Moved Permanently
Location: {0}
connection: Close

<!doctype html>
<h1>301 Moved Permanently</h1>
<p>Location: {0}</p>
"""

# Server root folder

ROOT_FOLDER = "www-data/"

def save_to_db(first, last):
    """Create a new user with given first and last name and store it into
    file-based database.

    For instance, save_to_db("Mick", "Jagger"), will create a new user
    "Mick Jagger" and also assign him a unique number.

    Do not modify this method."""

    existing = read_from_db()
    existing.append({
        "number": 1 if len(existing) == 0 else existing[-1]["number"] + 1,
        "first": first,
        "last": last
    })
    with open(PICKLE_DB, "wb") as handle:
        pickle.dump(existing, handle)


def read_from_db(criteria=None):
    """Read entries from the file-based DB subject to provided criteria

    Use this method to get users from the DB. The criteria parameters should
    either be omitted (returns all users) or be a dict that represents a query
    filter. For instance:
    - read_from_db({"number": 1}) will return a list of users with number 1
    - read_from_db({"first": "bob"}) will return a list of users whose first
    name is "bob".

    Do not modify this method."""
    if criteria is None:
        criteria = {}
    else:
        # remove empty criteria values
        for key in ("number", "first", "last"):
            if key in criteria and criteria[key] == "":
                del criteria[key]

        # cast number to int
        if "number" in criteria:
            criteria["number"] = int(criteria["number"])

    try:
        with open(PICKLE_DB, "rb") as handle:
            data = pickle.load(handle)

        filtered = []
        for entry in data:
            predicate = True

            for key, val in criteria.items():
                if val != entry[key]:
                    predicate = False

            if predicate:
                filtered.append(entry)

        return filtered
    except (IOError, EOFError):
        return []


def process_request(connection, address):
    """Process an incoming socket request.

    :param connection is a socket of the client
    :param address is a 2-tuple (address(str), port(int)) of the client
    """

    address, port = address

    client = connection.makefile("wrb")

    # Read and parse the request line
    request_line = client.readline().decode("utf-8").strip()

    # Read and parse headers
    headers = {}

    try:
        verb, uri, version = request_line.split(" ")
        assert verb == "GET" or verb == "POST", "Only GET and POST requests are supported"
        assert uri[0] == "/", "Invalid URI"
        assert version == "HTTP/1.1", "Invalid HTTP version"
        headers = parse_headers(client)
    except Exception as e:
        print("{0}: {1}] Error parsing request line {2}: {3}".format(address, port, request_line, e))
        client.write(RESPONSE_400.encode("utf-8"))
        client.close()
        return

    """
    if verb == "GET":
        uri, params = uri.split("?")
    """
    full_uri = ROOT_FOLDER + uri[1:]

    # Check for 301
    if isdir(full_uri):
        uri += "/" if uri[-1] != "/" else ""
        uri += "index.html"
        server_addr, server_port = connection.getsockname()
        if server_addr == "127.0.0.1":
            server_addr = "localhost"
        location = "http://{2}:{0}{1}".format(server_port, uri, server_addr)
        print(location)
        print("301")
        msg = RESPONSE_301.format(location)
        print(msg)
        client.write(msg.encode("utf-8"))
        client.close()
        return

    split_uri = uri.split("?")
    uri = split_uri[0]

    # GET app-list TODO finish this
    if uri[1:] == "app-index":
        if verb != "GET":
            print("Wrong params")
            client.write(RESPONSE_400.encode("utf-8"))
            client.close()
            return

        students = None
        if len(split_uri) > 1:
            params = split_uri[1]
            params = params.split("&")
            criteria = {}
            for param in params:
                try:
                    key_value = param.split("=")
                    key = key_value[0]
                    if (key == "first" or key == "last" or key == "number") and len(key_value) > 1:
                        criteria[key] = key_value[1]
                    #print(key + " => " + key_value[1])
                except Exception as e:
                    print("Wrong params {0}".format(e))
                    client.write(RESPONSE_400.encode("utf-8"))
                    client.close()
                    return
            students = read_from_db(criteria)
        else:
            students = read_from_db()

        file = open("www-data/app_list.html", "r")
        html_content = file.read()
        table_rows = ""
        for student in students:
            table_rows += TABLE_ROW % (student["number"], student["first"], student["last"])

        html_content = html_content.replace("{{students}}", table_rows)
        response_header = HEADER_RESPONSE_200 % ("text/html", len(html_content))
        client.write(response_header.encode("utf-8"))
        client.write(html_content.encode("utf-8"))
        client.close()
        return

    # Read and parse the body of the request (if applicable)
    # POST app-add
    if uri[1:] == "app-add":
        if verb != "POST":
            print("Wrong params")
            client.write(RESPONSE_400.encode("utf-8"))
            client.close()
            return

        to_read = int(headers["Content-Length"])
        params = client.read(to_read).decode("utf-8").strip()
        params = params.split("&")

        if len(params) != 2:
            print("Wrong params")
            client.write(RESPONSE_400.encode("utf-8"))
            client.close()
            return

        params_dict = {}
        for param in params:
            try:
                key, value = param.split("=")
                params_dict[key] = value
                print(key + " => " + value)
            except Exception as e:
                print("Wrong params{0}".format(e))
                client.write(RESPONSE_400.encode("utf-8"))
                client.close()
                return

        save_to_db(params_dict["first"], params_dict["last"])
        uri = "/app_add.html"
        full_uri = ROOT_FOLDER + uri[1:]

    # create the response
    try:
        with open(full_uri, "rb") as handle:
            response_body = handle.read()

        if mimetypes.guess_type(uri[1:])[0] is not None:
            mime_type = mimetypes.guess_type(uri[1:])[0]
        else:
            mime_type = "application/octet-stream"

        content_length = len(response_body)

        response_header = HEADER_RESPONSE_200 % (mime_type, content_length)
        client.write(response_header.encode("utf-8"))
        # Write the response back to the socket
        client.write(response_body)
    except Exception as e:
        print("Something went wrong {0}".format(e))
        client.write(RESPONSE_404.encode("utf-8"))

    # Closes file-like object
    client.close()


def parse_headers(client):
    headers = {}
    while True:
        line = client.readline().decode("utf-8").strip()
        if line == "":
            return headers
        key, value = line.split(":", 1)
        headers[key.strip()] = value.strip()

def main(port):
    """Starts the server and waits for connections."""

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("", port))
    server.listen(1)

    print("Listening on %d" % port)

    while True:
        connection, address = server.accept()
        print("[%s:%d] CONNECTED" % address)
        process_request(connection, address)
        connection.close()
        print("[%s:%d] DISCONNECTED" % address)


if __name__ == "__main__":
    main(8080)
