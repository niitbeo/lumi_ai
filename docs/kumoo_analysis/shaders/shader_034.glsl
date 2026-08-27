
    attribute vec3 a_position;
    attribute vec2 a_texCoord;
    varying vec2 v_texCoord;
    varying vec2 v_srcCoord;
    varying vec4 v_tempPosition;
    uniform mat4 u_mvpMatrix;
    void main()
    {
        v_tempPosition = u_mvpMatrix * vec4(a_position,1.0);
        v_texCoord = vec2(v_tempPosition.x/v_tempPosition.w*0.5 + 0.5, v_tempPosition.y/v_tempPosition.w*0.5 + 0.5);
        v_srcCoord = a_texCoord;
        gl_Position = vec4(a_texCoord.x*2.0 - 1.0, a_texCoord.y*2.0 - 1.0, 0.0, 1.0);
    }
