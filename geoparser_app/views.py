from django.shortcuts import render
import glob, os
import urllib2
from os.path import isfile
from django.shortcuts import render, render_to_response
from django.template import RequestContext
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse

from .forms import UploadFileForm
from .models import Document
from solr import IndexUploadedFilesText, QueryText, IndexLocationName, QueryLocationName, IndexLatLon, QueryPoints, IndexFile, create_core, IndexStatus

from tika import parser
from geograpy import extraction
from geopy.geocoders import Nominatim

geolocator = Nominatim()
flip = True

APP_NAME = "geoparser_app"
UPLOADED_FILES_PATH = "static/uploaded_files"
SUBDOMAIN = ""

def index(request):
    file_name = ""
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            instance = Document(docfile=request.FILES['file'])
            instance.save()
            file_name = str(instance.docfile).replace("{0}/{1}/".format(APP_NAME, UPLOADED_FILES_PATH),"")
            return HttpResponse(status=200, content="{{ \"file_name\":\"{0}\" }}".format(file_name), content_type="application/json")
    else:
        form = UploadFileForm()
    return render_to_response('index.html', {'form': form, 'subdomian':SUBDOMAIN},  RequestContext(request))


def upload_file(request, file_name):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            instance = Document(docfile=request.FILES['file'])
            instance.save()
    else:
        form = UploadFileForm()
    return render_to_response('index.html',  {'form': form, 'subdomian':SUBDOMAIN}, RequestContext(request))


def index_file(request, file_name):
    IndexFile(file_name)
    return HttpResponse(status=200)


def list_of_uploaded_files(request):
    '''
    Return list of uploaded files.
    '''
    files_list = []
    file_dir = os.path.realpath(__file__).split("views.py")[0]
    for f in os.listdir("{0}{1}".format(file_dir, UPLOADED_FILES_PATH)):
        if not f.startswith('.'):
            files_list.append(f)
    return HttpResponse(status=200, content="{0}".format(files_list))


def extract_text(request, file_name):
    '''
        Using Tika to extract text from given file
        and return the text content.
    '''
    if "none" in IndexStatus("text", file_name):
        parsed = parser.from_file("{0}/{1}/{2}".format(APP_NAME, UPLOADED_FILES_PATH, file_name))
        status = IndexUploadedFilesText(file_name, parsed["content"])
        if status[0]:
            return HttpResponse(status=200, content="Text extracted.")
        else:
            return HttpResponse(status=400, content="Cannot extract text.")
    else:
        return HttpResponse(status=200, content="Loading...")



def find_location(request, file_name):
    '''
        Find location name from extracted text using Geograpy.
    '''
    if "none" in IndexStatus("locations", file_name):
        text_content = QueryText(file_name)
        if text_content:
            e = extraction.Extractor(text=text_content)
            e.find_entities()
            status = IndexLocationName("local", file_name, e.places)
            if status[0]:
                return HttpResponse(status=200, content="Location/s found and index to Solr.")
            else:
                return HttpResponse(status=400, content=status[1])
        else:
            return HttpResponse(status=400, content="Cannot find location.")
    else:
        return HttpResponse(status=200, content="Loading...")



def find_latlon(request, file_name):
    '''
    Find latitude and longitude from location name using GeoPy.
    '''
    if "none" in IndexStatus("points", file_name):
        location_names = QueryLocationName(file_name)
        if location_names:
            points = []
            for location in location_names:
                try:
                    geolocation = geolocator.geocode(location)
                    points.append(
                        {'loc_name': location,
                        'position':{
                            'x': geolocation.longitude,
                            'y': geolocation.latitude
                        }
                        }
                    )
                except:
                    pass
            status = IndexLatLon(file_name, points)
            if status[0]:
                return HttpResponse(status=200, content="Latitude and longitude found.")
            else:
                return HttpResponse(status=400, content="Cannot find latitude and longitude.")
        else:
            return HttpResponse(status=400, content="Cannot find latitude and longitude.")
    else:
        return HttpResponse(status=200, content="Loading...")


def return_points(request, file_name):
    '''
        Returns geo point for give file
    '''
    points = QueryPoints(file_name)

    if points:
        return HttpResponse(status=200, content='['+points+']')
    else:
        return HttpResponse(status=400, content="Cannot find latitude and longitude.")


def query_crawled_index(request, indexed_path):
    '''
        To query crawled data that has been indexed into
        Solr or Elastichsearch and return location names
        Host should be without "http://"
    '''

    if "solr" in indexed_path.lower():
        try:
            url = "{0}/select?q=*%3A*&wt=json&rows=1".format(indexed_path)
            response = urllib2.urlopen(url)
            numFound = eval(response.read())['response']['numFound']
            text = eval(response.read())['response']['docs']
            e = extraction.Extractor(text=str(text))
            e.find_entities()
            status = IndexLocationName("solr", "solr_{0}".format(core_name), e.places)
            return HttpResponse(status=200, content=e.places)
        except Exception as e:
            return False
    else:
        pass
    
