
    attribute vec3 a_position;
    attribute vec2 a_texcoord;
    varying vec2 v_texcoord;
    varying vec4 v_tempPosition;
    uniform mat4 u_mvpMatrix;
    uniform int positionToTex;
    void main()
    {
        v_tempPosition = u_mvpMatrix * vec4(a_position,1.0);
        if(positionToTex == 1){
            vec4 temp = u_mvpMatrix * vec4(a_position,1.0);
            v_texcoord = vec2(temp.x/temp.w*0.5 + 0.5, temp.y/temp.w*0.5 + 0.5);
            gl_Position = vec4(a_texcoord.x*2.0 - 1.0, a_texcoord.y*2.0 - 1.0, 0.0, 1.0);
        }
        else{
            v_texcoord = a_texcoord;
            gl_Position = u_mvpMatrix * vec4(a_position,1.0);
        }
    }
