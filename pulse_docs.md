# Pulse Programming Language: The Complete Guide

Welcome to the definitive documentation for **Pulse** (`.pulse`), a lightweight, block-scoped programming language with native Python interoperability and an extremely powerful, declarative GUI engine.

---

## 1. Running Pulse

Pulse files use the `.pulse` extension. You can run them directly from your terminal using the built-in CLI:

```powershell
py -m pulse run .\path\to\your\file.pulse
```
or
```powershell
pulse run .\path\to\your\file.pulse
```

---

## 2. Syntax & Basic Types

Pulse has a very simple syntax without strict indentation rules. Every block begins with a colon `:` and closes with the keyword `end`.

### Comments
Comments begin with `!!` and extend to the end of the line.

```pulse
!! This is a comment
let x = 5 !! This is an inline comment
```

### Data Types and Operators
Pulse natively supports standard types like numbers, strings, and booleans.

- **Math Operators:** `+`, `-`, `*`, `/`, `%`
- **Comparisons:** `==`, `!=`, `<`, `<=`, `>`, `>=`
- **Logic Operators:** `and`, `or`, `not`

```pulse
let is_valid = not (5 > 10) and (2 == 2)
let name = "John" + " " + "Doe"
```

---

## 3. Variables & Scope

Variable scoping is one of Pulse's most unique features. There are **Globals** and **Locals**. Blocks do *not* automatically inherit the global scope!

### Global Variables (`let name = value`)
The `let` keyword *always* creates or modifies a **Global Variable**, no matter where it is used.

```pulse
let counter = 0 !! Global variable
```

### Local Variables (`name = value`)
Assigning without `let` creates a **Local Variable** scoped *only* to the current block. You cannot do this at the top level of a file.

### Importing Globals (`let(name)`)
Because blocks do not implicitly look up globals, you must **import** a global into a block's local scope using `let(var)` before you can read it.

```pulse
let counter = 0

func test_scope():
    !! We must import 'counter' to read it!
    let(counter) 
    
    !! Modifying the global requires 'let'
    let counter = counter + 1 
    
    !! Local variable (no let)
    my_local = 5 
end
```

---

## 4. Control Flow & Functions

### Functions
Define functions with `func name():` and end with `end`.

```pulse
func do_math():
    print("Doing math...")
end

do_math() !! Call the function
```

### If Statements
```pulse
if counter > 5:
    print("Greater than 5!")
end
```

### Loops (`while` and `until`)
Pulse has standard `while` loops, and inverted `until` loops (which run *until* a condition is true).

```pulse
let x = 0
while x < 5:
    let(x)
    let x = x + 1
end

let y = 0
until y == 5:
    let(y)
    let y = y + 1
end
```

---

## 5. Built-in Functions & Timers

### Standard Built-ins
- `print(args...)`: Prints to the terminal.
- `sleep(seconds)`: Pauses execution blocks (synchronous).
- `time()`: Returns the current UNIX timestamp.

### Asynchronous Timers (`after` and `every`)
Pulse has powerful built-in timer blocks. If used inside a GUI window, these are non-blocking!

- **`after <seconds>:`**: Executes the block once after a delay.
- **`every <seconds>:`**: Repeatedly executes the block on an interval.

```pulse
every 1:
    print("A second has passed!")
end

after 5:
    print("5 seconds have passed!")
end
```

---

## 6. Python Interoperability (`py.`)

Pulse can call *any* Python module, standard library, or built-in function dynamically using the `py.` prefix. You do not need to write wrapper code.

```pulse
!! Generate a random integer
let lucky_number = py.random.randint(1, 100)

!! Get python's current time
let current_time = py.time.ctime()

!! Use python's type casting
let as_string = py.str(lucky_number)

!! Use python's math module
let square_root = py.math.sqrt(16)
```

---

## 7. The GUI Engine

Pulse's crown jewel is its declarative GUI engine. You can build desktop apps simply by declaring blocks. All GUI elements support standard layout parameters:
`width`, `height`, `bg`/`background`, `fg`/`color`, `font`, `padx`, `pady`, `side`, `anchor`, `fill`, `expand`.

### `window`
Initializes the application window. You can only have one window.

```pulse
window "My App" width=500 height=400 bg="white":
    !! UI widgets go here
end
```

### `Label`
Displays text. You can pass a raw string, or a variable name to bind it!

```pulse
Label "Static Text" font="Arial 16 bold" color="red"

!! Bound Label
let counter = 5
let(counter)
Label counter  !! Will display '5'
```

### `Entry` and `Text` (Inputs)
- **`Entry "global_var"`**: A single-line text input. Automatically binds and updates the global variable named as a string.
- **`Text "global_var"`**: A multi-line text input.

```pulse
let username = ""
Entry "username" font="Arial 12" bg="lightgray"

let notes = ""
Text "notes" width=40 height=10
```

### `Image`
Loads a local image file. Standard `width` and `height` properties will safely resize the image.

```pulse
Image "path/to/logo.png" width=100 height=100
```

### `Button` (Must be a block)
Creates a clickable button. You can pass a function to execute `(func_name)` and/or put code directly inside its block. **Buttons must end with `:` and `end`**.

```pulse
func do_something():
    print("Clicked!")
end

Button "Click Me!"(do_something) bg="blue" fg="white":
    print("This also runs on click!")
end
```

### `update(variable)`
When you change a global variable that is bound to a GUI element (like a `Label` showing a variable, or an `Entry` bound to a string), the UI will not automatically visually refresh. You must call `update(var_name)` to push the new value to the screen.

```pulse
let status = "Waiting..."

func change_status():
    let(status)
    let status = "Complete!"
    update(status) !! Forces the UI Label to redraw with "Complete!"
end

window "App":
    let(status)
    Label status
    Button "Change"(change_status):
    end
end
```
