#ifdef GL_ES//for discriminate GLES & GL 
#else                                    
#define highp                            
#define mediump                          
#define lowp                             
#endif                                   
attribute highp   vec3  inVertex;
attribute highp vec2  inTexCoord;
varying highp vec2   textureCoordinate;
varying highp vec2   textureCoordinate2;
uniform highp mat3  transMat;
uniform highp mat4 MVP;
void main(){
gl_Position = MVP * vec4( inVertex, 1.0 );
textureCoordinate = inTexCoord;	
textureCoordinate2 = (transMat * vec3(inTexCoord, 1.0)).xy;	
}
