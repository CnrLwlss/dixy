#coding=utf-8
import urllib
import os.path

def get_header_only(f, source):
    header = {}
    if source == 'dixy':
        url_slug = 'http://research.ncl.ac.uk/colonyzer/QFAVis/GISDatasets/'
        fh = urllib.urlopen(url_slug+f, 'rU')
    elif source == 'dixy-pol':
        infile = os.path.join('/home/django/data/POL_v4/Scaled', f)
        fh = open(infile, 'rU')
    elif source == 'dixy-telo':
        infile = os.path.join('/home/django/data/telo', f)
        fh = open(infile, 'rU')
    for line in fh:
        if line.startswith('###'):
            break
        tokens = line.rstrip().split(':')
        header[tokens[0]] = tokens[1].strip()
    try:
        name_array = [header['Query background'],
           'at',
           header['Query treatment'],
           #'°C',
           ' C',
           'vs',
           header['Control background'],
           'at',
           header['Control treatment'],
           #'°C',
           ' C',
           ]
    except KeyError:
        try:
            name_array = [header['Query screen name'],
                'at',
                header['Query treatment'],
                #'°C',
                ' C',
                'vs',
                header['Control screen name'],
                'at',
                header['Control treatment'],
                #'°C',
                ' C',
                ]
        except KeyError:
            name_array = [header['y-axis screen name'],
                'vs',
                header['x-axis screen name'],
                ]
    name = ' '.join(name_array)
    header['name'] = name
    return header

class QFAParser:
    def __init__(self, xdata, ydata=None, xcol=None, ycol=None, fromURL=True):
        fh = self.getDataFile(xdata, fromURL)
        data_lines = fh.read().splitlines()
        fh.close()
        all_data = self.parse_data(data_lines)
        x_header = self.parse_header(data_lines)
        if ydata:
            fh = self.getDataFile(xdata, fromURL)
            y_data_lines = fh.read().splitlines()
            fh.close()
            y_header = self.parse_header(y_data_lines)
            #fh = open('/tmp/log', 'w')
            #fh.write(str(x_header)+'\n')
            #fh.write(str(y_header)+'\n')
            #fh.close()
            self.header = self.merge_headers(x_header, y_header, xcol, ycol)
            all_y_data = self.parse_data(y_data_lines)
            if xcol == 'x':
                self.x_data = all_data[1]
            elif xcol == 'y':
                self.x_data = all_data[2]
            if ycol == 'x':
                self.y_data = all_y_data[1]
            elif ycol == 'y':
                self.y_data = all_y_data[2]
            self.data_points = self.merge_data(self.x_data, self.y_data)
            self.regression_slope = self.get_slope(self.data_points)
            self.gene_names = self.merge_genes(all_data[0], all_y_data[0])
            self.q_values = all_data[4]
            for key in self.q_values.keys():
                self.q_values[key] = 1.0
        else:
            self.header = x_header
            #x axis is control data, can define column from header
            self.x_data = all_data[1]
            #y axis is query data
            self.y_data = all_data[2]
            #get y-name:gene-name mappings
            self.gene_names = all_data[0]
            #q-values for colouring significant points
            self.q_values = all_data[4]
            #need tuples for plotting
            self.data_points = self.merge_data(self.x_data, self.y_data)
            self.regression_slope = self.get_slope(self.data_points)

    def getDataFile(self, fname, fromURL=True):
        '''Read in GIS.txt file from server or from local file'''
        if fromURL:
            url_slug = 'http://research.ncl.ac.uk/colonyzer/QFAVis/GISDatasets/'
            fh = urllib.urlopen(url_slug+fname, 'r')
        else:
            fh=open(fname, 'r')
        return(fh)

    def update_metadata(self, metadata):
        '''Edit GIS.txt header dictionaries extracted from GIS.txt files generated by recent versions of QFA package to include keys expected by DIXY'''
        for k in metadata.keys():
            newk=k.replace("x-axis","Control")
            newk=newk.replace("y-axis","Query")
            metadata[newk]=metadata[k]
            newk=newk.replace("Control","x-axis")
            newk=newk.replace("Query","y-axis")
            metadata[newk]=metadata[k]            
        return(metadata)        
        
    def parse_header(self, fc):
        """Parse out significant information from QFA file header"""
        metadata = {}
        for line in fc:
            if line.startswith('###'):
                #end of metadata header
                break
            tokens = line.rstrip().split(':')
            metadata[tokens[0]] = tokens[1].strip()
        metadata=self.update_metadata(metadata)
        return metadata

    def parse_data(self, fc):
        """Parse data from QFA file, use col as column reference for values"""
        data = 0
        genes = {}
        x_points = {}
        y_points = {}
        gis_values = {}
        q_values = {}
        for line in fc:
            if data == 1:
                #process data
                if line.startswith('ORF'):
                    #this is the column headers
                    pass
                else:
                    tokens = line.split('\t')
                    orf_name = tokens[0]
                    genes[orf_name] = tokens[1]
                    x_points[orf_name] = tokens[6]
                    y_points[orf_name] = tokens[5]
                    gis_values[orf_name] = tokens[4]
                    q_values[orf_name] = tokens[3]
            if line.startswith('###'):
                #end of metadata header
                data = 1
        return (genes, x_points, y_points, gis_values, q_values)

    def merge_data(self, x, y):
        """Make coordinates from individual points"""
        coordinates = {}
        for key in x.keys():
            try:
                coordinate = (x[key], y[key])
            except KeyError:
                coordinate = (x[key], -20.0)
            coordinates[key] = coordinate
        for key in y.keys():
            if key not in coordinates.keys():
                coordinates[key] = (-20.0, y[key])
        return coordinates

    def lin_fit(self, x, y):
        '''Fits a linear fit of the form mx+b to the data'''
        import numpy
        #from scipy import optimize
        import scipy.optimize
        fitfunc = lambda params, x: params[0] * x    #create fitting function of form mx
        errfunc = lambda p, x, y: fitfunc(p, x) - y  #create error function for least squares fit
        init_a = 0.5                            #find initial value for a (gradient)
        init_p = numpy.array((init_a))  #bundle initial values in initial parameters
        #calculate best fitting parameters (i.e. m and b) using the error function
        p1, success = scipy.optimize.leastsq(errfunc, init_p.copy(),
                args = (numpy.array(x), numpy.array(y)))
        f = fitfunc(p1, x)          #create a fit with those parameters
        return p1, f

    def get_slope(self, coordinates):
        xpoints = []
        ypoints = []
        for key in coordinates.keys():
            xpoints.append(float(coordinates[key][0]))
            ypoints.append(float(coordinates[key][1]))
        #from scikits.statsmodels.api import OLS
        p, fit = self.lin_fit(xpoints, ypoints)
        #results = OLS(ypoints, xpoints).fit()
        #slope = results.params
        #print p, slope
        #print results.summary()
        return p[0]
    
    def merge_headers(self, x_header, y_header, xcol, ycol):
        header = x_header
        if xcol == 'y':
            header['Control treatment'] = x_header['Query treatment']
            header['Control medium'] = x_header['Query medium']
            header['Control background'] = x_header['Query background']
        if ycol == 'x':
            header['Query treatment'] = y_header['Control treatment']
            header['Query medium'] = y_header['Control medium']
            header['Query background'] = y_header['Control background']
        if ycol == 'y':
            header['Query treatment'] = y_header['Query treatment']
            header['Query medium'] = y_header['Query medium']
            header['Query background'] = y_header['Query background']
        return header
    
    def merge_genes(self, x_genes, y_genes):
        all_genes = {}
        for key in x_genes.keys():
            all_genes[key] = x_genes[key]
        for key in y_genes.keys():
            all_genes[key] = y_genes[key]
        return all_genes

if __name__ == '__main__':
    import pprint
    testdir="../../test_data"
    fnames=os.listdir(testdir)
    expected=["Control treatment","Control medium","Query treatment","Query medium"]
    for f in fnames:
        print(f)
        qfa=QFAParser(os.path.join(testdir,f),fromURL=False)
        for exp in expected:
            assert exp in qfa.header.keys()
        pprint.pprint(qfa.header)
    
