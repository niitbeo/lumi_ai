export function drawDebugLandmarks(context: CanvasRenderingContext2D, landmarks: number[][]) {
  context.save();
  context.fillStyle = "red";
  for (let i = 0; i < landmarks.length; i++) {
    const [x, y] = landmarks[i];
    context.beginPath();
    context.arc(x, y, 2, 0, 2 * Math.PI);
    context.fill();
    // Draw text
    context.fillStyle = "lime";
    context.font = "8px Arial";
    context.fillText(i.toString(), x + 2, y - 2);
    context.fillStyle = "red";
  }
  context.restore();
}
