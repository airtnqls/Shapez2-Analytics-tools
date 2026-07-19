#include <array>
#include <cstdint>
#include <iostream>
#include <vector>
#include <queue>
#include <algorithm>
using namespace std;
constexpr int L=7;
enum K:uint8_t{E=0,S=1,P=2,C=3};
struct Cell{K k=E; int8_t origin=-2;};
using Grid=array<array<Cell,4>,L+1>;
int leftq(int q){return(q+3)&3;} int rightq(int q){return(q+1)&3;}
bool occ(const Cell&c){return c.k!=E;} bool nonpin(const Cell&c){return c.k==S||c.k==C;}
uint32_t supportmask(const Grid&g,int H){
 uint32_t sup=0;for(int q=0;q<4;q++)if(occ(g[0][q]))sup|=1u<<q;
 bool ch=true;while(ch){ch=false;
  for(int r=1;r<H;r++)for(int q=0;q<4;q++)if(occ(g[r][q])&&(sup&(1u<<(4*(r-1)+q)))&&!(sup&(1u<<(4*r+q)))){sup|=1u<<(4*r+q);ch=true;}
  for(int r=0;r<H;r++)for(int q=0;q<4;q++)if(occ(g[r][q])&&g[r][q].k!=P&&!(sup&(1u<<(4*r+q))))for(int nq:{leftq(q),rightq(q)})if(occ(g[r][nq])&&g[r][nq].k!=P&&(sup&(1u<<(4*r+nq)))){sup|=1u<<(4*r+q);ch=true;break;}
  for(int r=0;r+1<H;r++)for(int q=0;q<4;q++)if(g[r][q].k==C&&g[r+1][q].k==C&&(sup&(1u<<(4*(r+1)+q)))&&!(sup&(1u<<(4*r+q)))){sup|=1u<<(4*r+q);ch=true;}
 }return sup;
}
void delete_crystal_components(Grid&g,int H,vector<pair<int,int>> seeds){
 bool vis[L+1][4]{};queue<pair<int,int>>qq;for(auto x:seeds){auto[r,q]=x;if(r>=0&&r<H&&occ(g[r][q])){vis[r][q]=true;qq.push(x);}}
 while(!qq.empty()){auto[r,q]=qq.front();qq.pop();if(g[r][q].k!=C)continue;for(int nq:{leftq(q),rightq(q)})if(!vis[r][nq]&&g[r][nq].k==C){vis[r][nq]=true;qq.push({r,nq});}for(int nr:{r-1,r+1})if(nr>=0&&nr<H&&!vis[nr][q]&&g[nr][q].k==C){vis[nr][q]=true;qq.push({nr,q});}}
 for(int r=0;r<H;r++)for(int q=0;q<4;q++)if(vis[r][q])g[r][q]=Cell{};
}
bool stable_pre(const Grid&g){uint32_t all=0;for(int r=0;r<L;r++)for(int q=0;q<2;q++)if(occ(g[r][q]))all|=1u<<(4*r+q);return all&&supportmask(g,L)==all;}
struct Mid {Grid g{}; uint8_t active=0;};
Mid pregravity(const Grid&pre){
 Grid g{};for(int q=0;q<2;q++)if(occ(pre[0][q]))g[0][q]={P,-1};for(int r=0;r<L;r++)for(int q=0;q<2;q++){g[r+1][q]=pre[r][q];if(occ(g[r+1][q]))g[r+1][q].origin=r;}
 vector<pair<int,int>> seeds;for(int q=0;q<2;q++)if(occ(g[L][q]))seeds.push_back({L,q});delete_crystal_components(g,L+1,seeds);for(int q=0;q<2;q++)g[L][q]=Cell{};
 while(true){auto sup=supportmask(g,L);vector<pair<int,int>>uc;for(int r=0;r<L;r++)for(int q=0;q<2;q++)if(occ(g[r][q])&&g[r][q].k==C&&!(sup&(1u<<(4*r+q))))uc.push_back({r,q});if(uc.empty())break;delete_crystal_components(g,L,uc);}
 auto sup=supportmask(g,L);uint8_t active=0;for(int r=0;r<L;r++)for(int q=0;q<2;q++)if(occ(g[r][q])&&g[r][q].k!=C&&!(sup&(1u<<(4*r+q))))active|=1<<q;
 return {g,active};
}
bool normalized_payload_stable(const Grid&g){
 auto sup=supportmask(g,L);int mn=L;Grid p{};bool any=false;
 for(int r=0;r<L;r++)for(int q=0;q<2;q++)if(occ(g[r][q])&&g[r][q].k!=C&&!(sup&(1u<<(4*r+q)))){mn=min(mn,r);any=true;}
 if(!any)return true;
 for(int r=mn;r<L;r++)for(int q=0;q<2;q++)if(occ(g[r][q])&&g[r][q].k!=C&&!(sup&(1u<<(4*r+q))))p[r-mn][q]=g[r][q];
 uint32_t all=0;for(int r=0;r<L;r++)for(int q=0;q<2;q++)if(occ(p[r][q]))all|=1u<<(4*r+q);
 return supportmask(p,L)==all;
}
string gs(const Grid&g){string z;for(int r=0;r<L;r++){if(r)z+=':';for(int q=0;q<2;q++)z+="-SPc"[g[r][q].k];}return z;}
int main(){
 const uint64_t total=1ull<<(4*L);uint64_t stable=0,active=0,withc=0,case_fixed=0,case_base=0,bad=0;
 for(uint64_t x=0;x<total;x++){
  Grid p{};uint64_t y=x;for(int r=0;r<L;r++)for(int q=0;q<2;q++){p[r][q].k=K(y&3);y>>=2;}
  if(p[L-1][0].k!=C&&p[L-1][1].k!=C)continue;if(!stable_pre(p))continue;stable++;
  auto m=pregravity(p);if(!m.active)continue;active++;auto sm=supportmask(m.g,L);
  int hc=-1;for(int r=0;r<L;r++)for(int q=0;q<2;q++)if(m.g[r][q].k==C)hc=max(hc,r);if(hc<0)continue;withc++;
  bool fixed_above=false;for(int r=hc+1;r<L;r++)for(int q=0;q<2;q++)if(occ(m.g[r][q])&&m.g[r][q].k!=C&&(sm&(1u<<(4*r+q))))fixed_above=true;
  if(fixed_above){case_fixed++;continue;}
  int best=-1;for(int q=0;q<2;q++)if(m.active&(1<<q))for(int r=0;r<L;r++)if(occ(m.g[r][q])&&(sm&(1u<<(4*r+q))))best=max(best,r);
  if(best>=hc){case_base++;continue;}
  bad++;cout<<"COMBINED_COUNTER pre="<<gs(p)<<" mid="<<gs(m.g)<<" active="<<(int)m.active<<" hc="<<hc<<" best="<<best<<"\n";return 0;
 }
 cout<<"NO_COMBINED_COUNTER L="<<L<<" stable="<<stable<<" active="<<active<<" withc="<<withc<<" fixed_above="<<case_fixed<<" base="<<case_base<<" bad="<<bad<<"\n";
}
