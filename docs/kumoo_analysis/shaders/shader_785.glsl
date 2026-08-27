
      #ifdef GL_ES
      #ifdef GL_FRAGMENT_PRECISION_HIGH
      precision highp float;
      #else
      precision mediump float;
      #endif
      #else
      #define highp
      #define mediump
      #define lowp
      #endif

      varying vec2 v_texcoord;
      varying vec2 v_coord;
      uniform sampler2D s_texture;
      uniform vec2 u_block_size;
      uniform vec2 u_origin_coord;
      uniform vec4 u_color_mesh1;
      uniform vec4 u_color_mesh2;

      void main()
      {
//          if(v_texcoord.x < 0.0 || v_texcoord.x > 1.0 || v_texcoord.y < 0.0 || v_texcoord.y > 1.0){
//            discard;
//          }
          vec4 tex_color = texture2D(s_texture,v_texcoord);

          float coord_x = mod(floor(0.5 * (v_coord.x - u_origin_coord.x) / u_block_size.x), 2.0);
          float coord_y = mod(floor(0.5 * (v_coord.y - u_origin_coord.y) / u_block_size.y), 2.0);


          //float coord_t = step(0.9, coord_x * coord_y);
          float coord_t = mix(0.0, 1.0, step(0.9, abs(coord_x - coord_y)));

          vec4 color_bg = u_color_mesh1 * coord_t + u_color_mesh2 * (1.0 - coord_t);

          //gl_FragColor = tex_color + color_bg * (1.0 - step(0.1, tex_color.a));
          gl_FragColor = mix(color_bg, tex_color, tex_color.a);
      }