#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <map>
#include <cmath>
using namespace std;

double splineInterpolation(const vector<double>& x, const vector<double>& y, double x_value) {

    int N = x.size()-1;

    //Compute h
    vector<double> h(N);   //N intervals
    for (int i = 0; i < N; i++) {
        h[i] = x[i+1] - x[i];
    }

    //Define matrix to be solved by Thomas algo
   vector <double> diag(N-1);
    vector<double> lower(N-2);
    vector<double> upper(N-2);
    vector<double> rhs(N-1);

    for (int i = 0; i < N-2; i++) {
        upper[i] = h[i+1];
        diag[i] = 2 * (h[i] + h[i+1]);      //The last element will be filled after this for loop.
        lower[i] = h[i+1];
        rhs[i] = 6 * ((y[i+2] - y[i+1])/h[i+1] - (y[i+1] - y[i])/h[i]);    //The last element will be filled after this for loop.
    }

    //Fill in the last elements of diag[] and rhs[]
    diag[N-2] = 2 * (h[N-2] + h[N-1]); 
    rhs[N-2] = 6 * ((y[N] - y[N-1])/h[N-1] - (y[N-1] - y[N-2])/h[N-2]);

    //Implement the Thomas algo 
    //(Step 1: forward sweep)
    for (int i = 1; i <= N-2; i++) {
        double w = lower[i-1]/diag[i-1];
        diag[i] = diag[i] - w * upper[i-1];
        rhs[i] = rhs[i] - w * rhs[i-1];
    } 

    //(Step 2: backward substitution)
    vector<double> m(N-1);
    m[N-2] = rhs[N-2]/diag[N-2];
    for (int i = N-3; i >= 0; i--) {
        m[i] = (rhs[i] - upper[i] * m[i+1]) / diag[i];
    }

    // Generate the second derivatives M by combining the boundary conditions
    // with the solution obtained from the Thomas algorithm 
    vector<double> M(N+1, 0);
    for (int i = 1; i < N; i++) {
        M[i] = m[i-1];
    }



    //Determine which interval contains x
    int j;  //Suppose x belongs to j-th interval (j = 0, 1, 2, ...)
    for (int i = 1; i < N+1; i++) {
        if (x_value <= x[i]) {
            j = i - 1;
            break;
        }
    }

    //Calculate the interpolated y value
    return M[j] / (6 * h[j]) * pow((x[j+1] - x_value), 3)
                   + M[j+1] / (6 * h[j]) * pow((x_value - x[j]), 3)
                   + (y[j] / h[j] - M[j] * h[j] / 6) * (x[j+1] - x_value)
                   + (y[j+1] / h[j] - M[j+1] * h[j] / 6) * (x_value - x[j]);

}

int main() {
    std::ifstream file("../data/nvda_calls_clean.csv");
    if(!file) return 1;

    int dateCol = 0;
    int valueCol = 8;
    int ivCol = 9;
    int dtmCol = 7;

    map<int, vector<double>> values;
    map<int, vector<double>> iv;


    std::string line;
    std::getline(file, line); // skip header

    while (std::getline(file, line)) {
        std::stringstream ss(line);
        std::string cell;
        int idx = 0;

        std::string date;
        std::string value;
        std::string ivValue;
        std::string dtm;

        while (std::getline(ss, cell, ',')) {
            if (idx == dateCol)  date  = cell;
            if (idx == dtmCol)   dtm   = cell;
            if (idx == valueCol) value = cell;
            if (idx == ivCol)    ivValue = cell;
            idx++;
        }

        if (!dtm.empty() && !value.empty() && !ivValue.empty()) {
            values[std::stoi(dtm)].push_back(std::stod(value));
            iv[std::stoi(dtm)].push_back(std::stod(ivValue));
        }
    }

    std::cout << "Nombre de valeurs: " << values.size() << "\n";
    std::cout << "Nombre de valeurs d'iv: " << iv.size() << "\n";

        //Enter a value of x
    double x_value;
    cout << "Enter your value of x: ";
    cin >> x_value;

    vector<double> dtmVec;
    vector<double> ivAtStrike;

    for (auto& [dtm, strikesVec] : values) {
        dtmVec.push_back(dtm);
        ivAtStrike.push_back(splineInterpolation(strikesVec, iv[dtm], x_value));
}

    cout << "Interpolated IV values:\n";
    for (size_t i = 0; i < dtmVec.size(); ++i) {
        cout << "DTM: " << dtmVec[i] << ", Interpolated IV: " << ivAtStrike[i] << "\n";
    }

    cout << "Which DTM do you want to use for interpolation? ";
    int chosenDTM;
    cin >> chosenDTM;

    double ivFinal = splineInterpolation(dtmVec, ivAtStrike, chosenDTM);
    cout << "Final interpolated IV for DTM " << chosenDTM << ": " << ivFinal << "\n";

    return 0;
}
