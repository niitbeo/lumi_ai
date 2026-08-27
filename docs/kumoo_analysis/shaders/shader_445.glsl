
attribute vec2 aPosition;
attribute vec2 aTexCoord;
varying vec2 texcoordOut;
uniform mat4 mvpMatrix;
void main()
{
    gl_Position = mvpMatrix * vec4(aPosition, 0.0, 1.0);
    texcoordOut = aTexCoord;
}

