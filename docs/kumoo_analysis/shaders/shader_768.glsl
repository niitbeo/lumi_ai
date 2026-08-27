
            attribute vec2 a_pos;
            attribute vec2 a_srcTex;
            attribute vec2 a_materialTex;

            varying vec2 v_srcTex;
            varying vec2 v_materialTex;

            void main()
            {
                v_srcTex = a_srcTex;
                v_materialTex = a_materialTex;
                gl_Position = vec4(a_pos, 0.0, 1.0);
            }
        