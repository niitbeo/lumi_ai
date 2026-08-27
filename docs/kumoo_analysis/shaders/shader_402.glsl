attribute vec3 a_position; 
             attribute vec3 a_normal; 
             uniform mat4 u_mvpMatrix; 
              uniform float u_strokeStrength; 
  			#define MAX_BONES 40 
			uniform mat4 u_bonesMatrixs[MAX_BONES];
 			attribute vec4 a_blendWeights;
				attribute vec4 a_blendIndices;
             mat4 getBoneMat()
             {
                if(a_blendWeights[0] != 0.0)
                     {
                         return u_bonesMatrixs[int (a_blendIndices[0])] * a_blendWeights[0]
                         + u_bonesMatrixs[int (a_blendIndices[1])] * a_blendWeights[1]
                         + u_bonesMatrixs[int (a_blendIndices[2])] * a_blendWeights[2]
                         + u_bonesMatrixs[int (a_blendIndices[3])] * a_blendWeights[3];
                     }
                else { return mat4(1.0);}            }
             void main(){    
              mat4 bone=getBoneMat();            vec3 normal=normalize(mat3(bone)*a_normal); 
                vec4 b_pos=bone*vec4(a_position,1.0); 
             vec4 pos=vec4(b_pos.xyz+normal*u_strokeStrength,1.0); 
              gl_Position=u_mvpMatrix*pos;}