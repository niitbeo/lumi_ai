
    attribute vec2 inputTextureCoordinate; attribute vec4 inputOffsetCoordinate;
    varying vec4 offsetCoord;

    void main() {
        offsetCoord = inputOffsetCoordinate;
        gl_Position = vec4(inputTextureCoordinate.x * 2.0 - 1.0,
                       inputTextureCoordinate.y * 2.0 - 1.0, 0.0, 1.0);
    }
