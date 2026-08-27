
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
      varying vec2 v_maskcoord;
      uniform sampler2D s_texture;
      uniform sampler2D s_mask;
      uniform vec2 u_mask_border_a;
      uniform vec2 u_mask_border_b;
      uniform vec2 u_mask_border_c;
      uniform vec2 u_mask_border_d;
      uniform float u_alpha;

      bool isPointInConvexQuad(vec2 p, vec2 a, vec2 b, vec2 c, vec2 d)
      {
        vec2 ab = b - a;
        vec2 bc = c - b;
        vec2 cd = d - c;
        vec2 da = a - d;
        vec2 ap = p - a;
        vec2 bp = p - b;
        vec2 cp = p - c;
        vec2 dp = p - d;
        float cross1 = ab.x * ap.y - ab.y * ap.x;
        float cross2 = bc.x * bp.y - bc.y * bp.x;
        float cross3 = cd.x * cp.y - cd.y * cp.x;
        float cross4 = da.x * dp.y - da.y * dp.x;

        bool allPositive = (cross1 > 0.0) && (cross2 > 0.0) && (cross3 > 0.0) && (cross4 > 0.0);
        bool allNegative = (cross1 < 0.0) && (cross2 < 0.0) && (cross3 < 0.0) && (cross4 < 0.0);
        return allPositive || allNegative;
      }

      vec4 get_mask_color(){
        if(!isPointInConvexQuad(v_maskcoord, u_mask_border_a, u_mask_border_b, u_mask_border_c, u_mask_border_d)){
          return vec4(0);
        }

        return texture2D(s_mask, v_maskcoord);
      }

      void main()
      {
          vec4 mask_color = get_mask_color();
          vec4 color = texture2D(s_texture,v_texcoord);
          float m = (1.0 - mask_color.r);
          float factor = color.a * u_alpha * m;
          gl_FragColor = vec4(color.rgb * m * u_alpha , factor);
          //gl_FragColor = vec4(mask_color.r, 0.0, 0.0, mask_color.r);
      }
      