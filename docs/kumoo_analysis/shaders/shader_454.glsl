attribute highp   vec3  inVertex;
attribute highp vec2  inTexCoord;
varying highp vec2   TexCoord;
uniform highp mat4 MVP;
void main(){
gl_Position = MVP * vec4( inVertex, 1.0 );
TexCoord = inTexCoord;	
}
