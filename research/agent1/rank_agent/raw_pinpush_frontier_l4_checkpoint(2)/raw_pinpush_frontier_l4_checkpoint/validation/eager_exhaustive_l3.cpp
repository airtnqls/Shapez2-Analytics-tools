#include <array>
#include <cstdint>
#include <iostream>
#include <vector>
#include <queue>
#include <algorithm>
using namespace std;
constexpr int L=3;
enum K:uint8_t{E=0,S=1,P=2,C=3};
struct Cell{K k=E; int8_t origin=-2;}; // -2 empty, -1 generated, >=0 source row
using Grid=array<array<Cell,4>,L+1>;
int leftq(int q){return (q+3)&3;} int rightq(int q){return(q+1)&3;}
bool occ(const Cell&c){return c.k!=E;} bool nonpin(const Cell&c){return c.k==S||c.k==C;}

uint16_t supportmask(const Grid&g,int H){
 uint16_t sup=0;
 for(int q=0;q<4;q++)if(occ(g[0][q]))sup|=1u<<q;
 bool ch=true;while(ch){ch=false;
  for(int r=1;r<H;r++)for(int q=0;q<4;q++)if(occ(g[r][q])&&(sup&(1u<<(4*(r-1)+q)))&&!(sup&(1u<<(4*r+q)))){sup|=1u<<(4*r+q);ch=true;}
  for(int r=0;r<H;r++)for(int q=0;q<4;q++)if(occ(g[r][q])&&g[r][q].k!=P&&!(sup&(1u<<(4*r+q)))){
    for(int nq:{leftq(q),rightq(q)})if(occ(g[r][nq])&&g[r][nq].k!=P&&(sup&(1u<<(4*r+nq)))){sup|=1u<<(4*r+q);ch=true;break;}
  }
  for(int r=0;r+1<H;r++)for(int q=0;q<4;q++)if(g[r][q].k==C&&g[r+1][q].k==C&&(sup&(1u<<(4*(r+1)+q)))&&!(sup&(1u<<(4*r+q)))){sup|=1u<<(4*r+q);ch=true;}
 }
 return sup;
}
void delete_crystal_components(Grid&g,int H,vector<pair<int,int>> seeds){
 bool vis[L+1][4]{};queue<pair<int,int>>qq;
 for(auto x:seeds){auto[r,q]=x;if(r>=0&&r<H&&occ(g[r][q])){vis[r][q]=true;qq.push(x);}}
 while(!qq.empty()){
  auto[r,q]=qq.front();qq.pop(); if(g[r][q].k!=C)continue;
  for(int nq:{leftq(q),rightq(q)})if(!vis[r][nq]&&g[r][nq].k==C){vis[r][nq]=true;qq.push({r,nq});}
  for(int nr:{r-1,r+1})if(nr>=0&&nr<H&&!vis[nr][q]&&g[nr][q].k==C){vis[nr][q]=true;qq.push({nr,q});}
 }
 for(int r=0;r<H;r++)for(int q=0;q<4;q++)if(vis[r][q])g[r][q]=Cell{};
}
vector<int> hcomp(const Grid&g,int r,int q,int H,uint16_t allowed){
 vector<int> out; if(!(allowed&(1u<<(4*r+q))))return out;
 if(g[r][q].k==P){out.push_back(q);return out;}
 bool seen[4]{};queue<int>qq;seen[q]=1;qq.push(q);
 while(!qq.empty()){int a=qq.front();qq.pop();out.push_back(a);for(int n:{leftq(a),rightq(a)})if(!seen[n]&&(allowed&(1u<<(4*r+n)))&&g[r][n].k!=P&&g[r][n].k!=C){seen[n]=1;qq.push(n);}}
 return out;
}
void gravity(Grid&g,int H){
 while(true){
  uint16_t sup=supportmask(g,H), all=0;for(int r=0;r<H;r++)for(int q=0;q<4;q++)if(occ(g[r][q]))all|=1u<<(4*r+q);
  uint16_t uns=all&~sup; if(!uns)break;
  vector<pair<int,int>> uc;for(int r=0;r<H;r++)for(int q=0;q<4;q++)if((uns&(1u<<(4*r+q)))&&g[r][q].k==C)uc.push_back({r,q});
  if(!uc.empty()){delete_crystal_components(g,H,uc);continue;}
  bool moved=false;uint16_t visited=0;
  for(int r=0;r<H;r++)for(int q=0;q<4;q++){
   uint16_t bit=1u<<(4*r+q);if(!(uns&bit)||(visited&bit)||!occ(g[r][q]))continue;
   auto comp=hcomp(g,r,q,H,uns);for(int x:comp)visited|=1u<<(4*r+x);
   int d=0;while(true){int nd=d+1;bool ok=true;for(int x:comp){int tr=r-nd;if(tr<0){ok=false;break;}if(occ(g[tr][x]) && tr!=r){ok=false;break;}}if(!ok)break;d=nd;}
   if(d){array<Cell,4> vals{};for(int x:comp){vals[x]=g[r][x];g[r][x]=Cell{};}for(int x:comp)g[r-d][x]=vals[x];moved=true;}
  }
  if(!moved)break;
 }
}

bool stable_pre(const Grid&g){uint16_t all=0;for(int r=0;r<L;r++)for(int q=0;q<4;q++)if(occ(g[r][q]))all|=1u<<(4*r+q);return all&&supportmask(g,L)==all;}

bool eager_bad(const Grid&pre, Grid &out, int &bad_s, array<int,4>&ds){
 Grid g{};
 for(int q=0;q<4;q++)if(occ(pre[0][q]))g[0][q]={P,-1};
 for(int r=0;r<L;r++)for(int q=0;q<4;q++){g[r+1][q]=pre[r][q];if(occ(g[r+1][q]))g[r+1][q].origin=r;}
 vector<pair<int,int>> seeds;for(int q=0;q<4;q++)if(occ(g[L][q]))seeds.push_back({L,q});
 delete_crystal_components(g,L+1,seeds);
 for(int q=0;q<4;q++)g[L][q]=Cell{};
 gravity(g,L);out=g;
 vector<pair<int,K>> seq[4];int bm=0;
 for(int q=0;q<4;q++){
  if(occ(pre[0][q]))bm|=1<<q;
  for(int r=0;r<L;r++)if(g[r][q].k==S||g[r][q].k==P)seq[q].push_back({r,g[r][q].k});
  if(bm>>q&1){if(seq[q].empty()||seq[q][0].first!=0||seq[q][0].second!=P)return false;seq[q].erase(seq[q].begin());}
 }
 int c[4]{};
 for(int s=0;s<L-1;s++){
  for(int q=0;q<4;q++)if(pre[s][q].k==S||pre[s][q].k==P)c[q]++;
  int mn=99;
  for(int q=0;q<4;q++){int e=0;for(auto [r,k]:seq[q])if(r<=s+1)e++;ds[q]=e-c[q];mn=min(mn,ds[q]);}
  if(mn>0){bad_s=s;return true;}
 }
 return false;
}
string gs(const Grid&g,int H=L){string z;for(int r=0;r<H;r++){if(r)z+=':';for(int q=0;q<4;q++)z+="-SPc"[g[r][q].k];}return z;}
int main(){uint64_t total=1ull<<(2*4*L),stable=0,topc=0;for(uint64_t x=0;x<total;x++){
 Grid p{};uint64_t y=x;for(int r=0;r<L;r++)for(int q=0;q<4;q++){p[r][q].k=K(y&3);y>>=2;}
 bool tc=false;for(int q=0;q<4;q++)tc|=p[L-1][q].k==C;if(!tc)continue;topc++;
 if(!stable_pre(p))continue;stable++;
 Grid o{};int s;array<int,4>d{};if(eager_bad(p,o,s,d)){cout<<"COUNTER "<<gs(p)<<" -> "<<gs(o)<<" s="<<s<<" d="<<d[0]<<d[1]<<d[2]<<d[3]<<"\n";return 0;}
 }
 cout<<"NO_COUNTER total="<<total<<" topc="<<topc<<" stable="<<stable<<"\n";
}
