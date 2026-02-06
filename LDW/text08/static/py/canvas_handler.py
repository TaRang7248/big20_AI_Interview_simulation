from pyscript import document
import js
from pyodide.ffi import create_proxy

canvas = document.getElementById('archCanvas')
ctx = canvas.getContext('2d')
painting = False

def startPosition(e):
    global painting
    painting = True
    draw(e)

def finishedPosition(e):
    global painting
    painting = False
    ctx.beginPath()

def draw(e):
    global painting
    if not painting:
        return
    
    rect = canvas.getBoundingClientRect()
    x = e.clientX - rect.left
    y = e.clientY - rect.top
    
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    
    ctx.lineTo(x, y)
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo(x, y)

def clearCanvas(e=None):
    ctx.clearRect(0, 0, canvas.width, canvas.height)

# Event Listeners
# proxy is needed for event callbacks in some versions, but create_proxy is safe
start_proxy = create_proxy(startPosition)
finish_proxy = create_proxy(finishedPosition)
draw_proxy = create_proxy(draw)
clear_proxy = create_proxy(clearCanvas)

canvas.addEventListener('mousedown', start_proxy)
canvas.addEventListener('mouseup', finish_proxy)
canvas.addEventListener('mousemove', draw_proxy)

# Expose clearCanvas to global scope so buttons can call it if needed
js.window.clearCanvas = clear_proxy
