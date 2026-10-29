// Display flow, FluidX3D setup. Included from FluidX3D/src/setup.cpp; `python src/cfd_tank.py prepare` wires it in.
// defines.hpp: EQUILIBRIUM_BOUNDARIES and SUBGRID on; BENCHMARK and every GRAPHICS mode off (prepare sets them).
// Every run setting comes from bin/reef_case.txt, written by `cfd_tank.py run`, so a new case needs no rebuild.
// Axes: x along the length from the left pane, y from the front glass, z up from the bottom glass. SI throughout.
// Box: glass and sand are no-slip solid; the running water line is a no-slip lid.
// Discs: openings on the left pane, held as equilibrium cells one layer in from the glass. Inlets push +x, outlets pull -x.
// Gyres: a solid tube standing off the back glass on a solid mount. Two slotted cages carry an outlet strip facing the aim
// and an intake strip on the opposite half, one cell layer outside the tube; both are equilibrium cells moving water along the aim.
// Rock: binary STL in tank metres, voxelized to solid. RFG: the R1 jet snaps among five tilted positions (US 11,071,990).
// Warm start: fluid cells start from a saved velocity field instead of still water.
// Names: windef.h defines IN, OUT, near and far as empty macros; none of them can name anything here.
#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <map>
#include <random>
#include <sstream>

namespace reef {

struct Disc {
	string name;
	bool inlet = true;
	float y = 0.0f, z = 0.0f, d = 0.0f, q = 0.0f; // center [m], diameter [m], flow [m^3/s]
	ulong cells = 0ull;
	float si_u = 0.0f; // face velocity that carries q through the voxelized area [m/s]
};

struct Gyre {
	string name;
	float x = 0.0f, z = 0.0f; // tube center in the glass plane [m]
	char axis = 'z'; // tube axis along x or z
	uint push = 0u; // push axis: 0 = x, 2 = z
	float sign = 1.0f; // push direction along it
	float q = 0.0f; // [m^3/s]
	float L = 0.0f, td = 0.0f, yc = 0.0f; // tube length, tube diameter, tube center from the front glass [m]
	float slot_in = 0.0f, slot_out = 0.0f; // slotted cage runs this far from the tube center, both ends [m]
	float mount_l = 0.0f, mount_w = 0.0f; // mount block along the tube and across the push, tube to glass [m]
	uint rows = 3u; // outlet strip height in cells, as an arc around the tube wall
	float aim = 0.0f; // outlet turned off the glass toward the room: 0 = along the glass, pi/2 = straight out [rad]
	ulong cells_in = 0ull, cells_out = 0ull;
	float u_in = 0.0f, u_out = 0.0f; // each strip carries q [m/s]
};

struct Rfg {
	bool on = false;
	float tilt = 0.0f, dwell_min = 1.0f, dwell_max = 5.0f, ramp = 0.25f; // [rad], [s], [s], [s]
	uint seed = 1u;
};

struct Case {
	std::map<string, string> kv;
	vector<Disc> discs;
	vector<Gyre> gyres;
	vector<string> stls;
	Rfg rfg;
	string warm;
	uint warm_N[3] = {0u, 0u, 0u};
	float f(const string& key) const {
		const auto it = kv.find(key);
		if(it==kv.end()) print_error("reef_case.txt: missing "+key);
		return std::stof(it->second);
	}
	string s(const string& key) const {
		const auto it = kv.find(key);
		if(it==kv.end()) print_error("reef_case.txt: missing "+key);
		return it->second;
	}
};

// key value per line, plus list lines:
// disc name inlet|outlet y z d q / gyre name x z x|z +x|-x|+z|-z q L td yc slot_in slot_out mount_l mount_w rows aim_deg
// stl path / rfg tilt_deg dwell_min dwell_max ramp seed / warm path Nx Ny Nz
inline Case read_case(const string& path) {
	Case c;
	std::ifstream file(path);
	if(!file.is_open()) print_error("cannot open "+path);
	string line;
	while(std::getline(file, line)) {
		if(line.empty()||line[0]=='#') continue;
		std::istringstream ss(line);
		string key;
		ss >> key;
		if(key=="disc") {
			Disc d;
			string kind;
			ss >> d.name >> kind >> d.y >> d.z >> d.d >> d.q;
			d.inlet = kind=="inlet";
			c.discs.push_back(d);
		} else if(key=="gyre") {
			Gyre g;
			string axis, push;
			float aim_deg = 0.0f;
			ss >> g.name >> g.x >> g.z >> axis >> push >> g.q >> g.L >> g.td >> g.yc >> g.slot_in >> g.slot_out >> g.mount_l >> g.mount_w >> g.rows >> aim_deg;
			g.aim = aim_deg*pif/180.0f;
			g.axis = axis[0];
			g.sign = push[0]=='-' ? -1.0f : 1.0f;
			g.push = push[1]=='x' ? 0u : 2u;
			if((g.axis=='x')==(g.push==0u)) print_error("gyre "+g.name+": push must cross the long side");
			c.gyres.push_back(g);
		} else if(key=="stl") {
			string p;
			std::getline(ss >> std::ws, p);
			c.stls.push_back(p);
		} else if(key=="rfg") {
			float tilt_deg = 0.0f;
			ss >> tilt_deg >> c.rfg.dwell_min >> c.rfg.dwell_max >> c.rfg.ramp >> c.rfg.seed;
			c.rfg.tilt = tilt_deg*pif/180.0f;
			c.rfg.on = tilt_deg>0.0f;
		} else if(key=="warm") {
			ss >> c.warm >> c.warm_N[0] >> c.warm_N[1] >> c.warm_N[2];
		} else {
			string value;
			ss >> value;
			c.kv[key] = value;
		}
	}
	return c;
}

inline vector<float> read_list(const string& csv) {
	vector<float> v;
	std::istringstream ss(csv);
	string item;
	while(std::getline(ss, item, ',')) if(!item.empty()) v.push_back(std::stof(item));
	return v;
}

inline string fmt(const double x, const int digits) {
	std::ostringstream ss;
	ss.setf(std::ios::fixed);
	ss.precision(digits);
	ss << x;
	return ss.str();
}

// fluid cell index j (1..N-2) sits (j-0.5) cells off the wall plane: mid-grid bounce-back puts the wall halfway into cell 0
inline float center(const uint j, const float dx) { return ((float)j-0.5f)*dx; }

// 0 none, 1 tube or mount, 4 the one-cell ring outside the tube wall over the slotted cages; off = ring angle from the aim, 0..pi
// main_setup turns ring cells into strips: per position along the tube, the `rows` cells nearest the aim are the outlet
// (a diagonal ring has extra cells, so an angle test alone would grow the outlet with the aim), the half opposite is the intake
inline uint gyre_part(const Gyre& g, const float xc, const float yc, const float zc, const float dx, float& off) {
	const float along = g.axis=='x' ? xc-g.x : zc-g.z;
	if(fabs(along)>0.5f*g.L) return 0u;
	const float f = g.yc-yc; // across the tube, positive toward the room
	const float p = g.sign*(g.push==0u ? xc-g.x : zc-g.z); // along the push, positive downstream
	const float R = 0.5f*g.td, d2 = sq(f)+sq(p);
	if(d2<=sq(R)) return 1u;
	if(f<=0.0f&&fabs(along)<=0.5f*g.mount_l&&fabs(p)<=0.5f*g.mount_w) return 1u;
	if(fabs(along)<g.slot_in||fabs(along)>g.slot_out||d2>sq(R+dx)) return 0u;
	off = fabs(remainderf(atan2f(f, p)-g.aim, 2.0f*pif));
	return 4u;
}

} // namespace reef

void main_setup() { // reef display flow; required extensions in defines.hpp: EQUILIBRIUM_BOUNDARIES, SUBGRID
	const string bin = get_exe_path();
	reef::Case c = reef::read_case(bin+"reef_case.txt");
	const string name = c.s("case");
	const float dx = c.f("dx_m"), Lx = c.f("Lx_m"), Ly = c.f("Ly_m"), Lz = c.f("Lz_m"), sand = c.f("sand_m");
	const float t_end = c.f("t_end_s"), t_report = c.f("report_s"), u_lat = c.f("u_lat");
	const float t_avg = c.f("avg_from_s"), t_sample = c.f("sample_s"); // time average from t_avg to the end, one sample per t_sample
	const vector<float> dumps = reef::read_list(c.s("dump_s"));
	const float si_nu = 1.0E-6f, si_rho = 1025.0f; // seawater at 78 F

	const uint Nx = (uint)lroundf(Lx/dx)+2u, Ny = (uint)lroundf(Ly/dx)+2u, Nz = (uint)lroundf(Lz/dx)+2u;

	// voxelize each disc on the x=1 layer first: the cells nearest its center, as many as its true area needs,
	// so every grid gets the same area, face velocity and jet momentum (a plain circle test gives 256 mm2 at 4 mm, 297 at 3 mm)
	vector<int> owner((ulong)Ny*(ulong)Nz, -1); // disc index per face cell, y+z*Ny
	float si_u_max = 0.0f;
	for(uint i=0u; i<(uint)c.discs.size(); i++) {
		reef::Disc& d = c.discs[i];
		vector<std::pair<float, ulong>> closest;
		for(uint z=1u; z<Nz-1u; z++) for(uint y=1u; y<Ny-1u; y++) {
			const float yc = reef::center(y, dx), zc = reef::center(z, dx);
			const float r2 = sq(yc-d.y)+sq(zc-d.z);
			if(zc>=sand&&owner[y+(ulong)z*Ny]<0&&r2<=sq(0.5f*d.d+2.0f*dx)) closest.push_back({r2, y+(ulong)z*Ny});
		}
		std::sort(closest.begin(), closest.end());
		const ulong want = (ulong)fmax(1.0f, roundf(0.25f*pif*sq(d.d)/sq(dx)));
		if(closest.size()<want) print_error("disc "+d.name+" runs into the sand or another disc at this dx");
		for(ulong j=0ull; j<want; j++) owner[closest[j].second] = (int)i;
		d.cells = want;
		d.si_u = d.q/((float)d.cells*dx*dx);
		si_u_max = fmax(si_u_max, d.si_u);
	}
	// gyre map: 1 solid, 2 intake, 3 outlet, per cell, with the owning gyre; count cells so each strip carries q through whole cells
	const ulong Ncells = (ulong)Nx*(ulong)Ny*(ulong)Nz;
	vector<uchar> gpart(Ncells, 0u), gown(Ncells, 0u);
	for(uint i=0u; i<(uint)c.gyres.size(); i++) {
		reef::Gyre& g = c.gyres[i];
		std::map<uint, vector<std::pair<float, ulong>>> ring; // along-the-tube index -> (angle from the aim, cell)
		for(uint z=1u; z<Nz-1u; z++) for(uint y=1u; y<Ny-1u; y++) for(uint x=1u; x<Nx-1u; x++) {
			const float zc = reef::center(z, dx);
			if(zc<sand) continue;
			float off = 0.0f;
			const uint part = reef::gyre_part(g, reef::center(x, dx), reef::center(y, dx), zc, dx, off);
			const ulong n = (ulong)x+((ulong)y+(ulong)z*(ulong)Ny)*(ulong)Nx;
			if(part==1u) { gpart[n] = 1u; gown[n] = (uchar)i; }
			if(part==4u) ring[g.axis=='x' ? x : z].push_back({off, n});
		}
		for(auto& [k, cells] : ring) {
			std::sort(cells.begin(), cells.end());
			for(ulong j=0ull; j<(ulong)cells.size(); j++) {
				const bool out = j<(ulong)g.rows, in = !out&&cells[j].first>=0.5f*pif;
				if(!out&&!in) continue;
				gpart[cells[j].second] = out ? 3u : 2u;
				gown[cells[j].second] = (uchar)i;
				if(out) g.cells_out++; else g.cells_in++;
			}
		}
		if(g.cells_in==0ull||g.cells_out==0ull) print_error("gyre "+g.name+" has no intake or outlet cells at this dx");
		g.u_in = g.q/((float)g.cells_in*dx*dx);
		g.u_out = g.q/((float)g.cells_out*dx*dx);
		si_u_max = fmax(si_u_max, fmax(g.u_in, g.u_out));
	}
	units.set_m_kg_s(1.0f, u_lat, 1.0f, dx, si_u_max, si_rho); // fastest opening runs at u_lat
	const float lbm_nu = units.nu(si_nu);
	print_info("Grid "+to_string(Nx)+" x "+to_string(Ny)+" x "+to_string(Nz)+", dt = "+reef::fmt(1.0E6*units.si_t(1ull), 1)+" us, nu = "+to_string(lbm_nu));
	for(const reef::Disc& d : c.discs) print_info(d.name+": "+to_string(d.cells)+" cells, "+reef::fmt(d.si_u, 3)+" m/s");
	for(const reef::Gyre& g : c.gyres) print_info(g.name+": intake "+to_string(g.cells_in)+" cells at "+reef::fmt(g.u_in, 3)+" m/s, outlet "+to_string(g.cells_out)+" cells ("+reef::fmt((double)g.cells_out*sq(dx)/sq(0.0254f), 2)+" in2) at "+reef::fmt(g.u_out, 3)+" m/s");

	LBM lbm(Nx, Ny, Nz, lbm_nu);
	// rock first: voxelizing reads flags back from the device, so the host edits below must come after it
	// STL in tank metres; lattice coordinate = cell index, and cell j's center is (j-0.5)*dx, so lattice = si/dx + 0.5
	for(const string& p : c.stls) {
		Mesh* mesh = read_stl(p, 1.0f/dx, float3x3(1.0f), float3(0.5f));
		print_info("Rock "+p+": "+reef::fmt(dx*(mesh->pmax.x-mesh->pmin.x)/0.0254f, 1)+" x "+reef::fmt(dx*(mesh->pmax.y-mesh->pmin.y)/0.0254f, 1)+" x "+reef::fmt(dx*(mesh->pmax.z-mesh->pmin.z)/0.0254f, 1)+" in");
		lbm.voxelize_mesh_on_device(mesh);
		delete mesh;
	}
	parallel_for(lbm.get_N(), [&](ulong n) { uint x=0u, y=0u, z=0u; lbm.coordinates(n, x, y, z);
		if(x==0u||x==Nx-1u||y==0u||y==Ny-1u||z==0u||z==Nz-1u) { lbm.flags[n] = TYPE_S; return; } // glass and lid
		const float xc = reef::center(x, dx), yc = reef::center(y, dx), zc = reef::center(z, dx);
		if(zc<sand) { lbm.flags[n] = TYPE_S; return; } // sand bed
		if(x==1u&&owner[y+(ulong)z*Ny]>=0) {
			const reef::Disc& d = c.discs[owner[y+(ulong)z*Ny]];
			lbm.flags[n] = TYPE_E;
			lbm.u.x[n] = units.u(d.inlet ? d.si_u : -d.si_u);
			return;
		}
		const uint part = gpart[n];
		if(part==1u) { lbm.flags[n] = TYPE_S; return; }
		if(part>=2u) { // both strips move water along the aim: the push, turned toward the room (-y)
			const reef::Gyre& g = c.gyres[gown[n]];
			lbm.flags[n] = TYPE_E;
			const float v = units.u(part==3u ? g.u_out : g.u_in);
			const float vp = g.sign*v*cos(g.aim);
			if(g.push==0u) lbm.u.x[n] = vp; else lbm.u.z[n] = vp;
			lbm.u.y[n] = -v*sin(g.aim);
			return;
		}
	});

	if(!c.warm.empty()) { // fluid cells start from a saved field (m/s: ux block, uy block, uz block); new solid stays still
		if(c.warm_N[0]!=Nx||c.warm_N[1]!=Ny||c.warm_N[2]!=Nz) print_error("warm start "+c.warm+" is a different grid");
		const ulong N = lbm.get_N();
		vector<float> w(3ull*N);
		std::ifstream f(c.warm, std::ios::binary);
		if(!f.is_open()) print_error("cannot open "+c.warm);
		f.read((char*)w.data(), (std::streamsize)(w.size()*sizeof(float)));
		parallel_for(N, [&](ulong n) {
			if(lbm.flags[n]!=0u) return;
			lbm.u.x[n] = units.u(w[n]); lbm.u.y[n] = units.u(w[N+n]); lbm.u.z[n] = units.u(w[2ull*N+n]);
		});
		print_info("Warm start from "+c.warm);
	}

	// RFG: the R1 face cells, re-aimed between chunks of steps
	vector<ulong> rfg_cells;
	float rfg_speed = 0.0f;
	for(const reef::Disc& d : c.discs) if(d.name=="R1") rfg_speed = units.u(d.si_u);
	if(c.rfg.on) for(ulong n=0ull; n<lbm.get_N(); n++) {
		uint x=0u, y=0u, z=0u; lbm.coordinates(n, x, y, z);
		if(x==1u&&owner[y+(ulong)z*Ny]>=0&&c.discs[owner[y+(ulong)z*Ny]].name=="R1") rfg_cells.push_back(n);
	}
	std::mt19937 rng(c.rfg.seed);
	auto rfg_dir = [&](const uint k) { const float phi = 2.0f*pif*(float)k/5.0f; return float3(cos(c.rfg.tilt), sin(c.rfg.tilt)*cos(phi), sin(c.rfg.tilt)*sin(phi)); };
	uint rfg_from = 0u, rfg_to = 0u;
	float rfg_switch = 0.0f, rfg_next = 0.0f; // when the last snap started, when the next one starts
	float3 rfg_last = float3(0.0f);

	const string out = bin+"reef_out/"+name+"/";
	std::filesystem::create_directories(out);
	{ // geometry once: flags as uint8 and a meta file for the plotter
		vector<uchar> buf(lbm.get_N());
		for(ulong n=0ull; n<lbm.get_N(); n++) buf[n] = lbm.flags[n];
		std::ofstream f(out+"flags.bin", std::ios::binary);
		f.write((const char*)buf.data(), (std::streamsize)buf.size());
		std::ofstream m(out+"meta.txt");
		m << "Nx " << Nx << "\nNy " << Ny << "\nNz " << Nz << "\ndx_m " << dx << "\nsand_m " << sand << "\nt_end_s " << t_end << "\n";
		for(const reef::Disc& d : c.discs) m << "disc " << d.name << " " << (d.inlet ? "inlet" : "outlet") << " " << d.y << " " << d.z << " " << d.d << " " << d.q << " " << d.cells << " " << d.si_u << "\n";
		for(const reef::Gyre& g : c.gyres) m << "gyre " << g.name << " " << g.x << " " << g.z << " " << g.axis << " " << (g.sign<0.0f ? "-" : "+") << (g.push==0u ? "x" : "z") << " " << g.q << " " << g.L << " " << g.td << " " << g.yc << " " << g.aim*180.0f/pif << " " << g.cells_in << " " << g.u_in << " " << g.cells_out << " " << g.u_out << "\n";
		for(const string& p : c.stls) m << "stl " << p << "\n";
	}
	std::ofstream rfg_log;
	if(c.rfg.on) { rfg_log.open(out+"rfg.csv"); rfg_log << "t_s,position\n"; }

	// stats: speed over fluid cells, in in/s, from a 0.1 in/s histogram
	const float INCH = 0.0254f; // not IN: windef.h defines IN empty
	const uint bins = 1000u;
	const float bin_w = 0.1f;
	std::ofstream stats(out+"stats.csv");
	stats << "t_s,wall_s,mean_in_s,p50_in_s,p90_in_s,max_in_s,below_1_in_s,below_3_in_s,ke_mJ\n";

	const auto wall0 = std::chrono::steady_clock::now();
	const float t_chunk = c.rfg.on ? fmin(0.02f, t_sample) : t_sample; // the RFG needs finer steps than the sampling
	const ulong steps = max(units.t(t_chunk), 1ull);
	const ulong t_last = units.t(t_end);
	uint next_dump = 0u;
	float next_report = t_report, next_sample = t_avg;
	// time average: mean velocity vector for direction, mean speed for strength (sloshing water has a small mean vector but real speed)
	vector<double> avg_u(4ull*lbm.get_N(), 0.0);
	uint samples = 0u;
	float avg_start = -1.0f;
	lbm.run(0u, t_last);
	while(lbm.get_t()<t_last) {
		if(c.rfg.on) { // snap among five positions, random hold, short ramp; write only when the aim moved
			const float t_now = units.si_t(lbm.get_t());
			if(t_now>=rfg_next) {
				rfg_from = rfg_to;
				rfg_to = (rfg_from+1u+(uint)(rng()%4u))%5u;
				rfg_switch = t_now;
				rfg_next = t_now+c.rfg.dwell_min+(c.rfg.dwell_max-c.rfg.dwell_min)*(float)(rng()%10000u)/10000.0f;
				rfg_log << reef::fmt(t_now, 2) << "," << rfg_to << "\n";
			}
			const float a = c.rfg.ramp>0.0f ? fmin((t_now-rfg_switch)/c.rfg.ramp, 1.0f) : 1.0f;
			const float3 dir = normalize((1.0f-a)*rfg_dir(rfg_from)+a*rfg_dir(rfg_to));
			if(length(dir-rfg_last)>1.0E-4f) {
				for(const ulong n : rfg_cells) { lbm.u.x[n] = rfg_speed*dir.x; lbm.u.y[n] = rfg_speed*dir.y; lbm.u.z[n] = rfg_speed*dir.z; }
				lbm.u.write_to_device(); // whole buffer: equilibrium cells read it, fluid cells recompute it from their DDFs
				rfg_last = dir;
			}
		}
		lbm.run(steps, t_last);
		const float t_si = units.si_t(lbm.get_t());
		const bool sampling = t_si>=t_avg&&t_si+0.5f*t_chunk>=next_sample;
		const bool reporting = t_si+0.5f*t_chunk>=next_report||lbm.get_t()>=t_last;
		if(!sampling&&!reporting) continue;
		lbm.u.read_from_device();
		if(sampling) {
			if(samples==0u) avg_start = t_si;
			next_sample = fmax(next_sample, t_si-0.5f*t_chunk)+t_sample;
			const ulong N = lbm.get_N();
			parallel_for(N, [&](ulong n) {
				const float ux = units.si_u(lbm.u.x[n]), uy = units.si_u(lbm.u.y[n]), uz = units.si_u(lbm.u.z[n]);
				avg_u[n] += ux; avg_u[N+n] += uy; avg_u[2ull*N+n] += uz; avg_u[3ull*N+n] += sqrt(sq(ux)+sq(uy)+sq(uz));
			});
			samples++;
		}
		if(!reporting) continue;
		next_report += t_report;
		vector<ulong> hist(bins+1u, 0ull);
		double sum = 0.0, ke = 0.0, vmax = 0.0;
		ulong count = 0ull, below1 = 0ull, below3 = 0ull;
		for(ulong n=0ull; n<lbm.get_N(); n++) {
			if(lbm.flags[n]!=0u) continue;
			const float s = units.si_u(sqrt(sq(lbm.u.x[n])+sq(lbm.u.y[n])+sq(lbm.u.z[n])))/INCH;
			sum += s; count++;
			ke += 0.5*(double)si_rho*sq((double)s*INCH)*(double)cb(dx);
			vmax = fmax(vmax, (double)s);
			if(s<1.0f) below1++;
			if(s<3.0f) below3++;
			hist[min((uint)(s/bin_w), bins)]++;
		}
		auto pct = [&](const double p) { ulong acc = 0ull; for(uint i=0u; i<=bins; i++) { acc += hist[i]; if((double)acc>=p*(double)count) return (i+0.5)*bin_w; } return (double)bins*bin_w; };
		const double wall = std::chrono::duration<double>(std::chrono::steady_clock::now()-wall0).count();
		stats << reef::fmt(t_si, 2) << "," << reef::fmt(wall, 1) << "," << reef::fmt(sum/(double)count, 3) << "," << reef::fmt(pct(0.5), 2) << "," << reef::fmt(pct(0.9), 2) << ","
		      << reef::fmt(vmax, 2) << "," << reef::fmt((double)below1/(double)count, 4) << "," << reef::fmt((double)below3/(double)count, 4) << "," << reef::fmt(1000.0*ke, 3) << "\n";
		stats.flush();
		while(next_dump<dumps.size()&&t_si+0.5f*t_report>=dumps[next_dump]) { // velocity field in m/s: ux block, uy block, uz block
			const float td = dumps[next_dump]; // whole seconds named as before (warm starts); animation frames carry a tenth
			std::ofstream f(out+"u_"+reef::fmt(td, td==floorf(td) ? 0 : 1)+"s.bin", std::ios::binary);
			vector<float> buf(lbm.get_N());
			for(ulong n=0ull; n<lbm.get_N(); n++) buf[n] = units.si_u(lbm.u.x[n]);
			f.write((const char*)buf.data(), (std::streamsize)(buf.size()*sizeof(float)));
			for(ulong n=0ull; n<lbm.get_N(); n++) buf[n] = units.si_u(lbm.u.y[n]);
			f.write((const char*)buf.data(), (std::streamsize)(buf.size()*sizeof(float)));
			for(ulong n=0ull; n<lbm.get_N(); n++) buf[n] = units.si_u(lbm.u.z[n]);
			f.write((const char*)buf.data(), (std::streamsize)(buf.size()*sizeof(float)));
			next_dump++;
		}
	}
	if(samples>0u) { // averaged field in m/s: mean ux, uy, uz blocks, then mean speed
		std::ofstream f(out+"u_avg.bin", std::ios::binary);
		vector<float> buf(lbm.get_N());
		for(uint b=0u; b<4u; b++) {
			for(ulong n=0ull; n<lbm.get_N(); n++) buf[n] = (float)(avg_u[(ulong)b*lbm.get_N()+n]/(double)samples);
			f.write((const char*)buf.data(), (std::streamsize)(buf.size()*sizeof(float)));
		}
		std::ofstream m(out+"meta.txt", std::ios::app);
		m << "avg_from_s " << avg_start << "\navg_to_s " << units.si_t(lbm.get_t()) << "\navg_samples " << samples << "\n";
	}
	print_info("Done: "+reef::fmt(units.si_t(lbm.get_t()), 1)+" s of tank time, "+to_string(samples)+" samples averaged");
}
