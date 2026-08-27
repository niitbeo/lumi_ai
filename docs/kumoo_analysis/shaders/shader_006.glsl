
            void main() {
                    texcoordOut = a_texcoord;
                    colorOut = vec4(a_color.rgb, 1.0);
                    positionOut = u_mvpMatrix * vec4(a_position, 1.0);
                    gl_Position = u_mvpMatrix * vec4(a_position, 1.0);
            }
            