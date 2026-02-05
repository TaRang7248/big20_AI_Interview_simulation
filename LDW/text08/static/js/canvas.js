// Canvas Logic using Fabric.js

let canvas;
let currentMode = 'select'; // select, rect, circle, text, arrow

// Initialize Canvas
document.addEventListener('DOMContentLoaded', () => {
    // Canvas element exists?
    const canvasEl = document.getElementById('architecture-canvas');
    if (!canvasEl) return;

    // Resize canvas to fit parent
    const parent = canvasEl.parentElement;
    canvasEl.width = parent.clientWidth;
    canvasEl.height = parent.clientHeight; // or fixed height

    // Init Fabric
    canvas = new fabric.Canvas('architecture-canvas', {
        width: parent.clientWidth - 32, // padding
        height: 600, // Fixed height for now
        backgroundColor: '#ffffff',
        selection: true
    });

    // Handle window resize
    window.addEventListener('resize', () => {
        const parent = document.querySelector('.canvas-panel');
        if (parent) {
             // Resize logic if needed, complex in fabric to keep content scale
             // For now, keep fixed simple size or reload
        }
    });

    console.log("Canvas Initialized");
});

// Tool Functions
function setMode(mode) {
    currentMode = mode;
    canvas.isDrawingMode = false;
    
    // Reset buttons visual state
    document.querySelectorAll('.tool-btn').forEach(btn => {
        btn.style.background = 'white';
        btn.style.color = '#334155';
    });
    
    // Highlight active (rough implementation, better with ID)
    const btnMap = {
        'select': 0, 'rect': 1, 'circle': 2, 'text': 3, 'arrow': 4
    };
    const btns = document.querySelectorAll('.tool-btn');
    if(btns[btnMap[mode]]) {
        btns[btnMap[mode]].style.background = '#e2e8f0';
    }
}

function addRect() {
    const rect = new fabric.Rect({
        left: 100,
        top: 100,
        fill: 'transparent',
        stroke: 'black',
        strokeWidth: 2,
        width: 100,
        height: 60,
        rx: 5, ry: 5 // rounded corners for architecture boxes
    });
    canvas.add(rect);
    setMode('select');
}

function addCircle() {
    const circle = new fabric.Circle({
        left: 200,
        top: 100,
        fill: 'transparent',
        stroke: 'black',
        strokeWidth: 2,
        radius: 40
    });
    canvas.add(circle);
    setMode('select');
}

function addText() {
    const text = new fabric.IText('Component', {
        left: 150,
        top: 150,
        fontSize: 16,
        fontFamily: 'Pretendard, sans-serif'
    });
    canvas.add(text);
    setMode('select');
}

function addArrow() {
    // Simplified arrow: a line with a triangle at the end
    // Or just a line for now to keep it simple
    // Fabric doesn't have built-in arrow, need custom path or group
    
    // Simple line
    const line = new fabric.Line([50, 50, 150, 50], {
        stroke: 'black',
        strokeWidth: 2
    });
    canvas.add(line);
    
    // Hint: "Use line for connections"
    console.log("Added Line");
    setMode('select');
}

function clearCanvas() {
    if(confirm('캔버스를 모두 지우시겠습니까?')) {
        canvas.clear();
        canvas.setBackgroundColor('#ffffff', canvas.renderAll.bind(canvas));
    }
}

function getCanvasImage() {
    return canvas.toDataURL({
        format: 'png',
        quality: 1.0
    });
}

// Bind Delete key to remove objects
document.addEventListener('keydown', (e) => {
    if (e.key === 'Delete' || e.key === 'Backspace') {
        const activeObjects = canvas.getActiveObjects();
        if (activeObjects.length) {
            canvas.discardActiveObject();
            activeObjects.forEach((obj) => {
                canvas.remove(obj);
            });
        }
    }
});
