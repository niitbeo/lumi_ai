
attribute vec3 a_position;
attribute vec2 a_texCoord;
varying vec2 v_srcCoord;
varying vec2 v_texCoord;
uniform mat4 u_mvpMatrix;
void main()
{
    v_texCoord = a_texCoord;
    gl_Position = u_mvpMatrix * vec4(a_position,1.0);
    v_srcCoord = vec2(gl_Position.x/gl_Position.w*0.5 + 0.5, gl_Position.y/gl_Position.w*0.5 + 0.5);
}
                                                    
