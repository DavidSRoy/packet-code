// Compact only the existing canvas; retain layouts, content, controls and navigation.
let canvasResizeObserver,canvasLayoutFrame;
function packCanvas(){const canvas=Q('#canvas');if(!canvas)return;const gap=parseFloat(getComputedStyle(canvas).rowGap)||12;const unit=8;for(const widget of canvas.querySelectorAll('.widget')){const rows=Math.ceil((widget.getBoundingClientRect().height+gap)/(unit+gap));widget.style.gridRowEnd='span '+Math.max(1,rows)}}
function observeCanvas(){canvasResizeObserver?.disconnect();const canvas=Q('#canvas');if(!canvas)return;const schedule=()=>{cancelAnimationFrame(canvasLayoutFrame);canvasLayoutFrame=requestAnimationFrame(packCanvas)};canvasResizeObserver=new ResizeObserver(schedule);for(const widget of canvas.querySelectorAll('.widget'))canvasResizeObserver.observe(widget);schedule()}
const unpackedRenderCanvas=renderCanvas;renderCanvas=function(){unpackedRenderCanvas();observeCanvas()};
observeCanvas();
