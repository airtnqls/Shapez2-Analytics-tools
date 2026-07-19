#include <array>
#include <cstdint>
#include <iostream>
#include <vector>
#include <queue>
#include <algorithm>
using namespace std;
constexpr int L=6;
enum K:uint8_t{E=0,S=1,P=2,C=3};
struct Cell{K k=E; int8_t origin=-2;}; // -2 empty, -1 generated, >=0 source row
using Grid=array<array<Cell,4>,L+1>;
int leftq(int q){return (q+3)&3;} int rightq(int q){return(q+1)&3;}
bool occ(const Cell&c){return c.k!=E;} bool nonpin(const Cell&c){return c.k==S||c.k==C;}

uint32_t supportmask(const Grid&g,int H){
 uint32_t sup=0;
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
vector<int> hcomp(const Grid&g,int r,int q,int H,uint32_t allowed){
 vector<int> out; if(!(allowed&(1u<<(4*r+q))))return out;
 if(g[r][q].k==P){out.push_back(q);return out;}
 bool seen[4]{};queue<int>qq;seen[q]=1;qq.push(q);
 while(!qq.empty()){int a=qq.front();qq.pop();out.push_back(a);for(int n:{leftq(a),rightq(a)})if(!seen[n]&&(allowed&(1u<<(4*r+n)))&&g[r][n].k!=P&&g[r][n].k!=C){seen[n]=1;qq.push(n);}}
 return out;
}
void gravity(Grid&g,int H){
 while(true){
  uint32_t sup=supportmask(g,H), all=0;for(int r=0;r<H;r++)for(int q=0;q<4;q++)if(occ(g[r][q]))all|=1u<<(4*r+q);
  uint32_t uns=all&~sup; if(!uns)break;
  vector<pair<int,int>> uc;for(int r=0;r<H;r++)for(int q=0;q<4;q++)if((uns&(1u<<(4*r+q)))&&g[r][q].k==C)uc.push_back({r,q});
  if(!uc.empty()){delete_crystal_components(g,H,uc);continue;}
  bool moved=false;uint32_t visited=0;
  for(int r=0;r<H;r++)for(int q=0;q<4;q++){
   uint32_t bit=1u<<(4*r+q);if(!(uns&bit)||(visited&bit)||!occ(g[r][q]))continue;
   auto comp=hcomp(g,r,q,H,uns);for(int x:comp)visited|=1u<<(4*r+x);
   int d=0;while(true){int nd=d+1;bool ok=true;for(int x:comp){int tr=r-nd;if(tr<0){ok=false;break;}if(occ(g[tr][x]) && tr!=r){ok=false;break;}}if(!ok)break;d=nd;}
   if(d){array<Cell,4> vals{};for(int x:comp){vals[x]=g[r][x];g[r][x]=Cell{};}for(int x:comp)g[r-d][x]=vals[x];moved=true;}
  }
  if(!moved)break;
 }
}


bool equal_grid(const Grid&a,const Grid&b,int H){
 for(int r=0;r<H;r++)for(int q=0;q<4;q++)if(a[r][q].k!=b[r][q].k)return false;
 return true;
}

bool half_stable_mask(const Grid&pre,int mask,const array<pair<int,int>,2>& boundaries){
 Grid original{},g{};
 for(int r=0;r<L;r++)for(int q=0;q<4;q++)if(mask>>q&1){original[r][q]=pre[r][q];g[r][q]=pre[r][q];}
 vector<pair<int,int>> seeds;
 for(int r=0;r<L;r++)for(auto [a,b]:boundaries){
   if(pre[r][a].k==C && pre[r][b].k==C){
     if(mask>>a&1)seeds.push_back({r,a});
     if(mask>>b&1)seeds.push_back({r,b});
   }
 }
 delete_crystal_components(g,L,seeds);
 gravity(g,L);
 return equal_grid(original,g,L);
}

bool cut_axis_stable(const Grid&pre,int axis){
 if(axis==0){
   array<pair<int,int>,2> b{pair<int,int>{0,3},pair<int,int>{1,2}};
   return half_stable_mask(pre,(1<<0)|(1<<1),b) && half_stable_mask(pre,(1<<2)|(1<<3),b);
 }
 array<pair<int,int>,2> b{pair<int,int>{0,1},pair<int,int>{3,2}};
 return half_stable_mask(pre,(1<<0)|(1<<3),b) && half_stable_mask(pre,(1<<1)|(1<<2),b);
}

bool stable_pre(const Grid&g){uint32_t all=0;for(int r=0;r<L;r++)for(int q=0;q<4;q++)if(occ(g[r][q]))all|=1u<<(4*r+q);return all&&supportmask(g,L)==all;}

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
  int positive=0; for(int q=0;q<4;q++) positive += ds[q]>0;
  if(positive>2){bad_s=s;return true;}
 }
 return false;
}

bool fixed_two_eager_bad(const Grid&pre, Grid&out, int&common_mask, array<int,4>&last_ds){
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
  if(bm>>q&1){if(seq[q].empty()||seq[q][0].first!=0||seq[q][0].second!=P)return true;seq[q].erase(seq[q].begin());}
 }
 int c[4]{};common_mask=15;
 for(int source=0;source<L-1;source++){
  for(int q=0;q<4;q++)if(pre[source][q].k==S||pre[source][q].k==P)c[q]++;
  int mask=0;
  for(int q=0;q<4;q++){int e=0;for(auto [r,k]:seq[q])if(r<=source+1)e++;last_ds[q]=e-c[q];if(last_ds[q]==0)mask|=1<<q;}
  common_mask &= mask;
 }
 return __builtin_popcount((unsigned)common_mask)<2;
}

string gs(const Grid&g,int H=L){string z;for(int r=0;r<H;r++){if(r)z+=':';for(int q=0;q<4;q++)z+="-SPc"[g[r][q].k];}return z;}
int old_main(){
 uint64_t total=1ull<<(2*4*L),stable=0,topc=0,cutstable=0;
 for(uint64_t x=0;x<total;x++){
  Grid p{};uint64_t y=x;for(int r=0;r<L;r++)for(int q=0;q<4;q++){p[r][q].k=K(y&3);y>>=2;}
  bool tc=false;for(int q=0;q<4;q++)tc|=p[L-1][q].k==C;if(!tc)continue;topc++;
  if(!stable_pre(p))continue;stable++;
  bool a0=cut_axis_stable(p,0),a1=cut_axis_stable(p,1);if(!a0&&!a1)continue;cutstable++;
  Grid o{};int cm=0;array<int,4>d{};
  if(fixed_two_eager_bad(p,o,cm,d)){
    cout<<"FIXED_TWO_EAGER_COUNTER "<<gs(p)<<" -> "<<gs(o)<<" common="<<cm<<" lastd="<<d[0]<<d[1]<<d[2]<<d[3]<<" axes="<<a0<<a1<<"\\n";return 0;
  }
 }
 cout<<"NO_COUNTER total="<<total<<" topc="<<topc<<" stable="<<stable<<" cutstable="<<cutstable<<"\\n";
}

uint8_t push_fallmask(const Grid&pre, Grid&out){
 Grid g{};
 for(int q=0;q<4;q++)if(occ(pre[0][q]))g[0][q]={P,-1};
 for(int r=0;r<L;r++)for(int q=0;q<4;q++){g[r+1][q]=pre[r][q];if(occ(g[r+1][q]))g[r+1][q].origin=r;}
 vector<pair<int,int>> seeds;for(int q=0;q<4;q++)if(occ(g[L][q]))seeds.push_back({L,q});
 delete_crystal_components(g,L+1,seeds);
 for(int q=0;q<4;q++)g[L][q]=Cell{};
 gravity(g,L);out=g;
 uint8_t m=0;
 for(int r=0;r<L;r++)for(int q=0;q<4;q++)if(occ(g[r][q])&&g[r][q].origin>=0&&g[r][q].k!=C&&r<g[r][q].origin+1)m|=1<<q;
 return m;
}
bool has_crystal(const Grid&g){for(int r=0;r<L;r++)for(int q=0;q<4;q++)if(g[r][q].k==C)return true;return false;}
struct Half{array<array<K,2>,L>a{};uint8_t c0=0,c1=0,fm=0;};
bool topmost_has_crystal(const Grid&g){for(int r=L-1;r>=0;r--){bool any=false,cr=false;for(int q=0;q<4;q++){any|=occ(g[r][q]);cr|=g[r][q].k==C;}if(any)return cr;}return false;}
int main(){
 vector<Half> both, anyfall;
 const uint64_t total=1ull<<(4*L);
 uint64_t stable_halves=0;
 for(uint64_t x=0;x<total;x++){
  Half h{};Grid g{};uint64_t y=x;
  for(int r=0;r<L;r++)for(int q=0;q<2;q++){h.a[r][q]=K(y&3);y>>=2;g[r][q].k=h.a[r][q];if(h.a[r][q]==C)(q?h.c1:h.c0)|=1<<r;}
  if(h.a[L-1][0]!=C&&h.a[L-1][1]!=C)continue;
  if(!stable_pre(g))continue;stable_halves++;
  Grid o{};h.fm=push_fallmask(g,o)&3;
  if(h.fm){anyfall.push_back(h);if(h.fm==3)both.push_back(h);}
 }
 uint64_t pairs=0,compatible=0,threefall=0,crystal_threefall=0,swapimp_threefall=0;
 for(const auto&A:both)for(const auto&B:anyfall){
  pairs++;
  if((A.c1&B.c0)||(A.c0&B.c1))continue;
  compatible++;
  Grid full{};for(int r=0;r<L;r++){full[r][0].k=A.a[r][0];full[r][1].k=A.a[r][1];full[r][2].k=B.a[r][0];full[r][3].k=B.a[r][1];}
  Grid out{};auto fm=push_fallmask(full,out);
  if(__builtin_popcount((unsigned)fm)<=2)continue;
  threefall++;
  if(!has_crystal(out))continue;
  crystal_threefall++;
  if(topmost_has_crystal(out)){
    cout<<"TOPCR_THREEFALL_COUNTER pre="<<gs(full)<<" out="<<gs(out)<<" fm="<<(int)fm<<"\n";return 0;
  }
  if(!cut_axis_stable(out,0)&&!cut_axis_stable(out,1)){
    swapimp_threefall++;
  }
 }
 cout<<"NO_COUNTER L="<<L
     <<" half_raw="<<total<<" stable_top_halves="<<stable_halves
     <<" anyfall_halves="<<anyfall.size()<<" bothfall_halves="<<both.size()
     <<" pairs="<<pairs<<" compatible="<<compatible
     <<" threefall="<<threefall<<" crystal_threefall="<<crystal_threefall
     <<" crystal_swapimp_threefall="<<swapimp_threefall<<"\n";
}
