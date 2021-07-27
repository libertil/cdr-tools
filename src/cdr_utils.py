import pathlib
import hashlib
import datetime

import requests

from requests.auth import HTTPBasicAuth


BASE_CDR_URL = "cdr.eionet.europa.eu"
BASE_BDR_URL = "bdr.eionet.europa.eu"
BASE_CDRTEST_URL = "cdrtest.eionet.europa.eu"
BASE_CDRSANDBOX_URL = "cdrsandbox.eionet.europa.eu"

URL_MAP = {"CDR": BASE_CDR_URL,
           "BDR": BASE_BDR_URL,
           "CDRTEST": BASE_CDRTEST_URL,
           "CDRSANDBOX": BASE_CDRSANDBOX_URL}


ENVELOPES_DATE_FIELDS = ["modifiedDate", "reportingDate", "statusDate"]
FILES_DATE_FIELDS = ["uploadDate"]
HISTORY_DATE_FIELDS = ["modified"]

DEFAULT_FIELDS = ["url", "title", "description", "countryCode", 
                  "isReleased", "reportingDate", "modifieddate", 
                  "periodstartyear", "periodendyear", 
                  "perioddescription", "isBlockedByQCError", 
                  "status", "statusDate", "creator", 
                  "hasUnknownQC", "files", "obligations"]

DELETE_ACTION = "delete"


def build_url(repo, eionet_login, secure):
    """ Builds a base url for a Rest call to CDR aAPI

    Parameters:
    repo (string): either CDR, CDRTEST or CDRSANDBOX
    eionet_login (tuple):   tuple of eionet login and password or None
    secure (boolean): if True https url will be returned if login  is provided 
    then https will be used regardless of secure

    returns: a url to  CDR api root    
    """

    # Avoid sending login info over non-secure http connection
    if secure or eionet_login: 
        scheme = "https:"
    else:
        scheme = "http:"

    if eionet_login:
        url = f"{scheme}//{eionet_login[0]}:{eionet_login[1]}@{URL_MAP[repo]}"
    else:
        url = f"{scheme}//{URL_MAP[repo]}"
    return url


def extract_base_url(envelope_url):
    """ Returns the root url of the envelope_url.  Used to acces the API """

    url_parts = requests.utils.urlparse(envelope_url)

    base_url = f"{url_parts.scheme}://{url_parts.netloc}"

    return base_url


def build_rest_query(base_url,
                     obligation,
                     country_code=None,
                     is_released=None,
                     reporting_date_start=None,
                     fields=None):
    """
    Builds a query to the CDR rest API to obtain envelope data
    for a specific obligation code.
    Optional query parameters are added to the query id specfied. 

    Parameters:
    base_url (string): API root url
    obligation (integer):  obligation code. Example 672 for AQ dataflow D
    is_released (boolean): if specified then only released (True) or unreleased 
                           envelopes will be returned 
    
    reporting_date_start (string):  DEPRECATED
    fields (array): names of the fields to extract
    
    Returns (string): a url to the Rest API to extrat the envelope    

    """ 

    url = f"{base_url}/api/envelopes?obligations={obligation}"
    
    if country_code:
        url = f"{url}&countryCode={country_code}"
    
    if is_released is not None:
        url = f"{url}&isReleased={int(is_released)}"
          
    #if reporting_date_start:
    #    url = f"{url}&reportingDateStart={reporting_date_start}"

    if fields:
        url = f"{url}&fields={fields}"
         
    return url

    
def download_file(url, dest_path, filename, eionet_login=None):
    """
    Downloads a file from a given url on CDR saving it as filename at the 
    dest_path if access to the envelope is restricted specify eionet_login
    
    Parameters:
    url (string): url to the file to download
    dest_path (string): path to the destination directory
    filename (string): name of the file once downloaded

    Returns (string):  SHA256 hash signature of the file
    """

    req = requests.get(url, auth=eionet_login, stream=True)
    req.raise_for_status()
    pathlib.Path(dest_path).mkdir(parents=True, exist_ok=True)
    dest_file = pathlib.Path(dest_path).joinpath(filename)
    handle = open(dest_file, "wb")
    
    # Write file and calculate SHA256 hash
    sha256_hash = hashlib.sha256()
    for chunk in req.iter_content(chunk_size=512):
        if chunk:  # filter out keep-alive new chunks
            handle.write(chunk)
            sha256_hash.update(chunk)
    
    return sha256_hash.hexdigest()


def get_envelopes_rest(obligation,
                       repo="CDR",
                       eionet_login=None, 
                       secure=True,
                       is_released=None,
                       country_code=None,
                       reporting_date_start=None,
                       convert_dates=True,
                       fields=DEFAULT_FIELDS
                       ):
    
    base_url = build_url(repo, eionet_login, secure)
    
    url = build_rest_query(base_url, obligation,
                           is_released=is_released,
                           country_code=country_code,
                           reporting_date_start=reporting_date_start,
                           fields=",".join(fields))

    r = requests.get(url, auth=eionet_login)
    
    envelopes = r.json()["envelopes"]
    
    # Convert date
    if convert_dates:
        convert_date_fields(envelopes, ENVELOPES_DATE_FIELDS, 
                            {"history": HISTORY_DATE_FIELDS})
           
    return envelopes


def get_envelope_by_url(envelope_url, 
                        eionet_login=None,
                        convert_dates=True,
                        repo="CDR",
                        fields=DEFAULT_FIELDS):

    base_url = build_url(repo, eionet_login, True)
    
    url = f"{base_url}/api/envelopes?url={envelope_url}"
    
    r = requests.get(url, auth=eionet_login)
    
    envelopes = r.json()["envelopes"]

    # Convert date
    if convert_dates:
        convert_date_fields(envelopes, ENVELOPES_DATE_FIELDS)
       
    return envelopes[0]


def convert_date_fields(items, date_fields, sub_elements={}):
    for df in date_fields:  
        for it in items:
            if df in it:
                if it[df] != "" and it[df] is not None:
                    it[df] = datetime.datetime.strptime(it[df],
                                                        "%Y-%m-%dT%H:%M:%SZ")
                else:
                    it[df] = None

                    
def create_envelope(repo,
                    country_code,
                    obligation_code,
                    title="",
                    descr="",
                    year="",
                    endYear="",
                    partofyear="",
                    locality="",
                    eionet_login=None,
                    debug=False):

    cdr_user, cdr_pwd = eionet_login
    
    base_url = build_url(repo, None, True)
    request_url = (f"{base_url}/{country_code}/{obligation_code}/"
                   "manage_addEnvelope")
    
    if debug:
        print(f"Request url {request_url}")
    
    data = {"title": title,
            "descr": descr,
            "year": year,
            "endyear": endYear,
            "partofyear": partofyear,
            "locality": locality} 

    session = requests.Session()
    session.auth = (cdr_user, cdr_pwd)
    headers = {"Accept": "application/json"}

    response = session.post(request_url, data=data, headers=headers) 
    
    if debug:
        print(f"Response {response}")
    
    if response.status_code == 201:
        return response.json()
    else:
        return {"errors": [f"http response {response.status_code}"]}


def delete_envelope(envelope_url, 
                    eionet_login=None):
    """ Deletes the envelope

    envelope_url (string): url of the envelope
    eionet_login: tuple of login name and password 
                  to access restricted envelopes
    
    
    Returns: HTTP response of the get request
    """

    cdr_login, cdr_pwd = eionet_login
    
    base_url = "/".join(envelope_url.split("/")[0:-1])+"/"
    env_code = envelope_url.split("/")[-1]
    data = {"ids:list": env_code, "manage_delObjects:method": "Delete"}
    
    session = requests.Session()
    session.auth = (cdr_login, cdr_pwd)
    response = session.post(base_url, data=data)

    return response.status_code 

    
def activate_envelope(envelope_url, 
                      eionet_login=None,
                      workitem_id=0):
    """ Activates the envelope
    
    envelope_url (string): url of the envelope
    eionet_login: tuple of login name and password 
                  to access restricted envelopes
    
    
    Returns: HTTP response of the get request
    """

    cdr_login, cdr_pwd = eionet_login

    request_url = (f"{envelope_url}/activateWorkitem?workitem_id={workitem_id}"
                   f"&DestinationURL={envelope_url}")
    auth = HTTPBasicAuth(cdr_login, cdr_pwd)
    
    response = requests.get(request_url, auth=auth)

    return response


def start_envelope_qa(envelope_url,
                      eionet_login,
                      workitem_id):

    """ Starts QA on the envelope
    
    envelope_url (string): url of the envelope
    eionet_login: tuple of login name and password 
                  to access restricted envelopes
    
    
    Returns: HTTP response of the get request
    """

    cdr_login, cdr_pwd = eionet_login

    request_url = (f"{envelope_url}/completeWorkitem?workitem_id={workitem_id}"
                   f"&release_and_finish=0&DestinationURL={envelope_url}")
    auth = HTTPBasicAuth(cdr_login, cdr_pwd)
    
    response = requests.get(request_url, auth=auth)  
    
    return response
    
    
def upload_file(envelope_url,
                file, 
                eionet_login=None,
                debug=False):
    """ Uploads a file in a envelope

    envelope_url (string): url of the envelope
    file (string or file): path to the file or file object
    eionet_login: tuple of login name and password 
                  to access restricted envelopes
    debug (boolean): set to True to print the HTTP response

    """

    cdr_user, cdr_pwd = eionet_login

    request_url = f"{envelope_url}/manage_addDocument"
    
    if type(file) is str:
        files = {"file": open(file, "rb")}
    elif isinstance(file, dict): 
        files = file

    auth = HTTPBasicAuth(cdr_user, cdr_pwd)
    response = requests.post(request_url, files=files, auth=auth) 
    
    if debug:
        print(response)

     
# curl "https://cdrtest.eionet.europa.eu/api/envelopes?url=https://cdrtest.eionet.europa.eu/ro/colwydrga/envxde78w&fields=feedbacks"
def get_feedbacks(envelope_url,
                  eionet_login=None):
    """ Extract the feedbacks from the speciafied envelope

    Parameters:
    envelope_url (string): url of the envelope
    eionet_login: tuple of login name and password 
                  to access restricted envelopes

    Returns (string): json representation of the envelope feedbacks
    """
    
    cdr_login, cdr_pwd = eionet_login
    
    base_url = extract_base_url(envelope_url)
    
    request_url = (f"{base_url}/api/envelopes?url={envelope_url}"
                   "&fields=feedbacks,countryCode,periodStartYear,obligations")
    auth = HTTPBasicAuth(cdr_login, cdr_pwd)
    
    response = requests.get(request_url, auth=auth)  

    if response.status_code == 200:
        return response.json()["envelopes"][0]
    else:
        return {"errors": [f"http response {response.status_code}"]}


def get_current_workitem(envelope_url,
                         eionet_login=None):
    """ Return most recent element of the history of the envelope

    Parameters:
    envelope_url (string): url of the envelope
    eionet_login: tuple of login name and password 
                  to access restricted envelopes

    Returns (string): json representation of the most recent element 
                      in envelope history

    """
    request_url = f"{envelope_url}/get_current_workitem"

    if eionet_login:
        cdr_login, cdr_pwd = eionet_login
        auth = HTTPBasicAuth(cdr_login, cdr_pwd)
    else:
        auth = None

    response = requests.get(request_url, auth=auth)

    if response.status_code == 200:
        return response.json()
    else:
        return {"errors": [f"http response {response.status_code}"]}


def get_history(envelope_url,
                eionet_login=None):
    """ Extract the history from the specified envelope

    Parameters:
    envelope_url (string): url of the envelope
    eionet_login: tuple of login name and password 
                  to access restricted envelopes

    Returns (string): json representation of the envelope history
    """

    base_url = extract_base_url(envelope_url)
    
    request_url = (f"{base_url}/api/envelopes?url={envelope_url}"
                   "&fields=history,countryCode,periodStartYear,obligations")

    if eionet_login:
        cdr_login, cdr_pwd = eionet_login
        auth = HTTPBasicAuth(cdr_login, cdr_pwd)
    else:
        auth = None

    response = requests.get(request_url, auth=auth)  

    if response.status_code == 200:
        res = response.json()["envelopes"][0]
        convert_date_fields(res["history"], HISTORY_DATE_FIELDS)
        return res["history"]
    else:
        return {"errors": [f"http response {response.status_code}"]}
