# https://stackoverflow.com/a/44029435

# PyQt is GPL v3 licenced
from PyQt5.QtWidgets import QSizePolicy, QWidget, QVBoxLayout
# matplotlib uses a custom licence that is BSD compatible
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as Canvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.widgets import Cursor
import matplotlib

# Ensure using PyQt5 backend
matplotlib.use('QT5Agg')


class MplCanvas(Canvas):
    """
    The actual matplotlib canvas used for plotting. The self.fig and self.ax parameters can be used like a normal
    matplotlib figure and axis handle to produce whatever plots are necessary
    """
    def __init__(self):
        self.fig = Figure()
        self.fig.set_tight_layout(True)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlim(-20, 20)
        self.ax.set_ylim(0, 103)
        Canvas.__init__(self, self.fig)
        Canvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        Canvas.updateGeometry(self)

class MplToolbar(NavigationToolbar):
    """
    Small inherited toolbar class to remove some of the tools we don't need
    """
    toolitems = [t for t in NavigationToolbar.toolitems if
                 t[0] in ('Pan', 'Zoom', 'Home', 'Save')]


class MplWidget(QWidget):
    """
    Small wrapper widget to house a matplotlib canvas
    """
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)   # Inherit from QWidget
        self.canvas = MplCanvas()                  # Create canvas object
        self.toolbar = MplToolbar(self.canvas, self)

        self.vbl = QVBoxLayout()         # Set box for plotting
        self.vbl.addWidget(self.toolbar)
        self.vbl.addWidget(self.canvas)
        self.setLayout(self.vbl)
        self.legend = None
        self.setMouseTracking(True)
        #self.set_cursor()

    def reset_axis(self,xmin=-0.5,xmax=7.5,ymin=0,ymax=100):
        self.canvas.ax.cla()
        self.canvas.ax.set_xlim(xmin, xmax)
        self.canvas.ax.set_ylim(ymin, ymax)

    def set_cursor(self,color='red',linewidth=2,linestyle=":"):
        """
        Sets the cursor to be used to highlight the exact location on canvas that is being hovered over
        :param color: Color of the cursor
        :param linewidth: Linewidth of the cursor
        :param linestyle: Linestyle of the cursor
        :return:
        """
        self.cursor = Cursor(self.canvas.ax, useblit=True, color=color, linewidth=linewidth, linestyle=linestyle)