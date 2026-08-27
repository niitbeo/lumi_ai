
                                                       attribute vec3 a_Position;
                                                       attribute vec2 a_UV;
                                                       
                                                       uniform mat4 u_mvpMatrix;
                                                       varying vec2 v_materialUV;
                                                       
                                                       void main()
                                                       {
                                                           v_materialUV = a_UV;
                                                           gl_Position = u_mvpMatrix * vec4(a_Position,1.0);
                                                       }
                                                       
                                                       