import tkinter as tk
from tkinter import messagebox, ttk
from enum import Enum
import uuid
import random

# ---------------------------
# Global Style and Constants
# ---------------------------

# Colors for different node types (for non-input nodes)
NODE_COLORS = {
    "LOGIC": "#A5D6A7",   # light green
    "OUTPUT": "#FFE082"   # amber
}

# A palette for input nodes (so they are not all the same)
INPUT_NODE_COLORS = [
    "#81D4FA",  # light blue
    "#FF8A80",  # light red
    "#80D8FF",  # light cyan
    "#CFD8DC"   # blue grey
]

# Node Types
NODE_INPUT = "INPUT"
NODE_OUTPUT = "OUTPUT"
NODE_LOGIC = "LOGIC"

# Data Types
class DataType(Enum):
    INTEGER = "Integer"
    FLOAT = "Float"
    TEXT = "Text"
    BOOLEAN = "Boolean"

# Global Variables for nodes and connections
nodes = []           # List of Node objects
# Each connection is stored as a dictionary: {"start": Node, "end": Node, "line_id": canvas_line_id}
connections = []
selected_node = None
dragging_connection = None  # Will store the temporary line id

# ---------------------------
# Node Class Definition
# ---------------------------
class Node:
    def __init__(self, canvas, x, y, node_type, label=""):
        self.id = str(uuid.uuid4())
        self.canvas = canvas
        self.x, self.y = x, y
        self.node_type = node_type
        self.label = label if label else node_type
        self.data_type = DataType.FLOAT
        self.value = 0 if node_type == NODE_INPUT else None
        self.inputs = []
        self.outputs = []
        self.custom_code = "" if node_type == NODE_LOGIC else None

        # Choose fill color based on node type.
        # For input nodes, choose a random color from our palette.
        if node_type == NODE_INPUT:
            fill_color = random.choice(INPUT_NODE_COLORS)
        else:
            fill_color = NODE_COLORS.get(node_type, "lightblue")

        # Create visual elements for the node
        self.rect = canvas.create_rectangle(
            x - 40, y - 20, x + 40, y + 20,
            fill=fill_color,
            outline="#424242", width=2,
            tags="node"
        )
        self.text = canvas.create_text(
            x, y,
            text=self.label,
            font=("Segoe UI", 10),
            fill="#212121",
            tags="node"
        )
        # Edge: a small circle for starting connections
        self.edge = canvas.create_oval(
            x + 35, y - 5, x + 45, y + 5,
            fill="#EF5350",  # a red-ish tone
            outline="",
            tags="edge"
        )

        # Bind events for moving nodes and double-click actions
        for item in [self.rect, self.text]:
            canvas.tag_bind(item, "<B1-Motion>", self.drag)
            # For input nodes, double-click to set value.
            if node_type == NODE_INPUT:
                canvas.tag_bind(item, "<Double-1>", self.set_value)
            elif node_type == NODE_LOGIC:
                canvas.tag_bind(item, "<Double-1>", self.open_code_editor)
            # Bind right-click to show the context menu (for deletion)
            canvas.tag_bind(item, "<Button-3>", self.show_context_menu)

        # Also bind the edge to show the node's menu
        canvas.tag_bind(self.edge, "<Button-3>", self.show_context_menu)

        # Bind events for the connection edge (hover and drag)
        canvas.tag_bind(self.edge, "<Enter>", lambda e: canvas.config(cursor="hand2"))
        canvas.tag_bind(self.edge, "<Leave>", lambda e: canvas.config(cursor=""))
        canvas.tag_bind(self.edge, "<ButtonPress-1>", self.start_connection)
        canvas.tag_bind(self.edge, "<B1-Motion>", self.draw_temp_connection)
        canvas.tag_bind(self.edge, "<ButtonRelease-1>", self.complete_connection)

    def show_context_menu(self, event):
        """Show a right-click menu with deletion option."""
        menu = tk.Menu(root, tearoff=0)
        menu.add_command(label="Delete Node", command=lambda: self.delete_node())
        menu.tk_popup(event.x_root, event.y_root)

    def delete_node(self):
        """Delete this node and any connections involving it."""
        # Delete node's canvas items
        self.canvas.delete(self.rect)
        self.canvas.delete(self.text)
        self.canvas.delete(self.edge)
        # Remove any connections that include this node
        global connections
        connections = [conn for conn in connections if conn["start"] != self and conn["end"] != self]
        # Remove the node from the global list
        if self in nodes:
            nodes.remove(self)
        update_connections()

    def open_code_editor(self, event):
        """Opens a code editor window for logic nodes using ttk widgets."""
        if self.node_type != NODE_LOGIC:
            return

        editor_window = tk.Toplevel(root)
        editor_window.title("Logic Node Editor")
        editor_window.geometry("600x400")
        editor_window.transient(root)

        # Use a ttk.Frame as the container
        container = ttk.Frame(editor_window, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        # Display available inputs
        input_frame = ttk.LabelFrame(container, text="Available Inputs")
        input_frame.pack(fill=tk.X, pady=5)
        input_text = ""
        for i, input_node in enumerate(self.inputs):
            input_text += f"input_{i}: {input_node.data_type.value} = {input_node.value}\n"
        if not input_text:
            input_text = "No inputs connected"
        ttk.Label(input_frame, text=input_text, justify=tk.LEFT).pack(anchor="w", padx=5, pady=5)

        # Code editor label and text widget
        ttk.Label(container, text="Enter your custom logic:", font=("Segoe UI", 10)).pack(anchor="w", pady=(10, 2))
        code_editor = tk.Text(container, height=15, font=("Consolas", 10))
        code_editor.pack(fill=tk.BOTH, expand=True, pady=5)
        code_editor.configure(highlightbackground="#B0BEC5", relief="flat")

        # Insert existing code or a template
        if self.custom_code:
            code_editor.insert("1.0", self.custom_code)
        else:
            template = (
                "# Available variables: input_0, input_1, etc. (based on connected inputs)\n"
                "# Store your result in the variable 'result'\n"
                "# Example:\n"
                "if input_0 > 10:\n"
                "    result = 'High'\n"
                "else:\n"
                "    result = 'Low'\n"
            )
            code_editor.insert("1.0", template)

        def save_code():
            self.custom_code = code_editor.get("1.0", tk.END).strip()
            editor_window.destroy()
            # Update node display to indicate custom logic
            self.canvas.itemconfig(self.text, text="Logic\n(Custom)")

        ttk.Button(container, text="Save", command=save_code).pack(pady=10)

    def validate_connection(self, target_node):
        """Validates if a connection between nodes is allowed."""
        if target_node == self:
            return False
        if target_node in self.outputs or self in target_node.inputs:
            return False
        if target_node.node_type == NODE_OUTPUT and len(target_node.inputs) >= 1:
            messagebox.showerror("Error", "Output node can have only 1 input")
            return False
        return True

    def compute(self):
        """Computes the node's output value based on its type and inputs."""
        if self.node_type == NODE_INPUT:
            return self.value

        if self.node_type == NODE_LOGIC:
            if not self.custom_code:
                messagebox.showerror("Error", "No custom code defined for logic node")
                return None
            # Prepare input variables for custom code execution
            input_values = {}
            for i, input_node in enumerate(self.inputs):
                input_values[f"input_{i}"] = input_node.compute()
            try:
                namespace = input_values.copy()
                exec(self.custom_code, {}, namespace)
                if "result" in namespace:
                    return namespace["result"]
                else:
                    messagebox.showerror("Error", "No 'result' variable set in custom code")
                    return None
            except Exception as e:
                messagebox.showerror("Error", f"Error in custom code: {str(e)}")
                return None

        elif self.node_type == NODE_OUTPUT:
            if not self.inputs:
                return None
            return self.inputs[0].compute()

        return None

    def set_value(self, event):
        """Opens a configuration dialog for input nodes using ttk widgets."""
        if self.node_type != NODE_INPUT:
            return

        dialog = tk.Toplevel(root)
        dialog.title("Input Node Configuration")
        dialog.geometry("300x200")
        dialog.transient(root)
        container = ttk.Frame(dialog, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="Select Data Type:", font=("Segoe UI", 10)).pack(pady=(5, 2))
        data_type_var = tk.StringVar(value=self.data_type.value)
        data_type_dropdown = ttk.Combobox(
            container,
            textvariable=data_type_var,
            state="readonly",
            values=[dt.value for dt in DataType]
        )
        data_type_dropdown.pack(pady=5)

        ttk.Label(container, text="Enter Value:", font=("Segoe UI", 10)).pack(pady=(10, 2))
        value_entry = ttk.Entry(container)
        if self.value is not None:
            value_entry.insert(0, str(self.value))
        value_entry.pack(pady=5)

        def save_input():
            try:
                selected_type = DataType(data_type_var.get())
                input_value = value_entry.get().strip()
                if selected_type == DataType.INTEGER:
                    self.value = int(input_value)
                elif selected_type == DataType.FLOAT:
                    self.value = float(input_value)
                elif selected_type == DataType.TEXT:
                    self.value = input_value
                elif selected_type == DataType.BOOLEAN:
                    self.value = input_value.lower() in ["true", "1", "yes"]
                self.data_type = selected_type
                self.canvas.itemconfig(
                    self.text,
                    text=f"{self.label}\n{selected_type.value}: {self.value}"
                )
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Invalid Input", f"Please enter a valid {selected_type.value} value")

        ttk.Button(container, text="Save", command=save_input).pack(pady=10)

    def drag(self, event):
        # Calculate movement delta
        dx = event.x - self.x
        dy = event.y - self.y
        self.x, self.y = event.x, event.y

        # Move all associated canvas items
        self.canvas.move(self.rect, dx, dy)
        self.canvas.move(self.text, dx, dy)
        self.canvas.move(self.edge, dx, dy)
        update_connections()

    def start_connection(self, event):
        global selected_node, dragging_connection
        selected_node = self
        # Create a temporary line for the connection
        dragging_connection = self.canvas.create_line(
            self.x + 40, self.y, event.x, event.y,
            fill="#424242", dash=(4, 2), width=2, tags="temp_line"
        )

    def draw_temp_connection(self, event):
        if dragging_connection:
            self.canvas.coords(dragging_connection, self.x + 40, self.y, event.x, event.y)

    def complete_connection(self, event):
        global selected_node, dragging_connection
        target_node = get_node_at(event.x, event.y)
        if target_node and self.validate_connection(target_node):
            # Append the new connection as a dictionary.
            connections.append({"start": self, "end": target_node, "line_id": None})
            self.outputs.append(target_node)
            target_node.inputs.append(self)
            update_connections()
        self.canvas.delete("temp_line")
        dragging_connection = None
        selected_node = None

# ---------------------------
# Helper Functions
# ---------------------------
def get_node_at(x, y):
    """Return the node under the given (x, y) coordinates, if any."""
    for node in nodes:
        if (node.x - 40 <= x <= node.x + 40) and (node.y - 20 <= y <= node.y + 20):
            return node
    return None

def create_node(node_type):
    """Create a new node of the given type and place it on the canvas."""
    # Place nodes in a grid-like pattern
    padding_x, padding_y = 100, 100
    spacing_x, spacing_y = 150, 100
    count = len(nodes)
    x = padding_x + (count % 3) * spacing_x
    y = padding_y + (count // 3) * spacing_y
    node = Node(canvas, x, y, node_type)
    nodes.append(node)

def update_connections():
    """Redraw all connections between nodes and bind right-click for deletion."""
    canvas.delete("line")
    for conn in connections:
        start = conn["start"]
        end = conn["end"]
        line_id = canvas.create_line(
            start.x + 40, start.y,
            end.x - 40, end.y,
            arrow=tk.LAST, fill="#616161", width=2, tags=("line", "conn_line")
        )
        conn["line_id"] = line_id
        # Bind right-click on the connection line to delete it.
        canvas.tag_bind(line_id, "<Button-3>", lambda event, conn=conn: delete_connection(event, conn))

def delete_connection(event, conn):
    """Delete the specified connection."""
    if conn in connections:
        connections.remove(conn)
        update_connections()

def execute_flow():
    """Execute the flow by computing output nodes and updating their display."""
    output_nodes = [node for node in nodes if node.node_type == NODE_OUTPUT]
    if not output_nodes:
        messagebox.showwarning("Warning", "No output nodes in the flow")
        return

    for node in output_nodes:
        result = node.compute()
        if result is None:
            display_text = "OUTPUT\nN/A"
        else:
            if isinstance(result, (int, float)):
                display_text = f"OUTPUT\n{result:.2f}"
            elif isinstance(result, str):
                display_text = f"OUTPUT\n{result}"
            elif isinstance(result, bool):
                display_text = f"OUTPUT\n{result}"
            else:
                display_text = f"OUTPUT\n{result}"
        canvas.itemconfig(node.text, text=display_text)

# ---------------------------
# Main Application Setup
# ---------------------------
root = tk.Tk()
root.title("Flow-Based Programming")
root.geometry("1000x700")
root.minsize(800, 600)

# Use ttk and a modern theme
style = ttk.Style(root)
style.theme_use("clam")

# Main container frames: left sidebar for controls and right canvas for drawing nodes
main_frame = ttk.Frame(root)
main_frame.pack(fill=tk.BOTH, expand=True)

# Left Sidebar for controls
sidebar = ttk.Frame(main_frame, width=200, padding=(10, 10))
sidebar.pack(side=tk.LEFT, fill=tk.Y)
sidebar.pack_propagate(False)

ttk.Label(sidebar, text="Nodes", font=("Segoe UI", 12, "bold")).pack(pady=(0, 10))

# Button style for consistency
btn_style = {"padding": 5}

# Buttons for creating nodes
ttk.Button(sidebar, text="Input Node", command=lambda: create_node(NODE_INPUT), **btn_style).pack(fill=tk.X, pady=5)
ttk.Button(sidebar, text="Logic Node", command=lambda: create_node(NODE_LOGIC), **btn_style).pack(fill=tk.X, pady=5)
ttk.Button(sidebar, text="Output Node", command=lambda: create_node(NODE_OUTPUT), **btn_style).pack(fill=tk.X, pady=5)

# A separator before the run button
ttk.Separator(sidebar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)
ttk.Button(sidebar, text="Run Flow", command=execute_flow, **btn_style).pack(fill=tk.X, pady=5)

# Optionally, additional controls or a status bar can be added here.

# Right Frame for the canvas
canvas_frame = ttk.Frame(main_frame)
canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

canvas = tk.Canvas(canvas_frame, bg="white")
canvas.pack(fill=tk.BOTH, expand=True)

# Start the main event loop
root.mainloop()
