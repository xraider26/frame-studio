import hashlib
from pathlib import Path
import tempfile
import unittest
from studio.execution_evidence import validate_execution


class ReferencePathTests(unittest.TestCase):
    def test_different_local_path_requires_matching_observed_bytes_not_path_spelling(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'server.png';file.write_bytes(b'actual-reference-bytes')
            job={'handoff':{'prompt':'world','negative_prompt':'','references':[{'id':'ref','version':1,'slot':'style','path':str(file)}]}}
            execution={'tool':'image_gen.imagegen','prompt':'world','negative_prompt':'','references':[{'id':'ref','version':1,'slot':'style'}],
                       'arguments':{'referenced_image_paths':['different-client/reference.png']},
                       'reference_files':[{'path':'different-client/reference.png','sha256':hashlib.sha256(file.read_bytes()).hexdigest()}]}
            self.assertEqual(validate_execution(job,execution)['state'],'match')
            execution['reference_files'][0]['sha256']='0'*64
            self.assertEqual(validate_execution(job,execution)['references_match'],'mismatch')
            del execution['reference_files']
            self.assertEqual(validate_execution(job,execution)['references_match'],'mismatch')
