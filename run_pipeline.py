########################################################################
#
# Run the ontology mapping pipeline on a set of key-value pairs 
# that describe a biological sample
#
########################################################################

from optparse import OptionParser
import json
import sys
from collections import defaultdict
import dill
import datetime
from multiprocessing import Pool
import pkg_resources as pr
from map_sra_to_ontology import config
from map_sra_to_ontology import pipeline_components as pc


def main():
    parser = OptionParser()
    parser.add_option("-f", "--key_value_file",
                      help="JSON file storing key-value pairs describing sample",
                      dest="input_filename")
    parser.add_option("-o", "--output", help="Output filename",
                      dest="output_filename", type="str", default="")
    parser.add_option("-i", "--init", help="init dill file",
                      dest="init_dill",
                      default=pr.resource_filename(__name__, "pipeline_init.dill"))
    parser.add_option("-k", "--keywords",
                      help="specified mapping keywords json",
                      dest="keywords_filename", type="str", default="")
    parser.add_option("-n", "--processes", help="# of processes",
                      dest="processes", type="int", default=1)
    parser.add_option("-d", "--debug", help="debug mode",
                      dest="dbg", action="store_true")
    (options, args) = parser.parse_args()

    input_f    = options.input_filename
    output_f   = options.output_filename
    init_dill  = options.init_dill
    processes  = options.processes
    debug_mode = options.dbg
    keywords_f = options.keywords_filename

    # Map key-value pairs to ontologies
    with open(input_f, "r", encoding="utf-8") as f:
        biosample_json = json.load(f)

    tag_to_vals = []
    ct = datetime.datetime.now()
    sys.stderr.write('[{}] Parsing BioSample JSON\n'.format(ct))
    for tag_to_val in biosample_json:
        entry = {}
        entry["accession"] = tag_to_val["accession"]
        for k in tag_to_val["characteristics"]:
            entry[k] = tag_to_val["characteristics"][k][0]["text"]
        tag_to_vals.append(entry)

    # Load ontologies
    ct = datetime.datetime.now()
    sys.stderr.write('[{}] Initializing pipeline.\n'.format(ct))
    dill.load_session(init_dill)
    # ont_name_to_ont_id = {
    #     "UBERON":"12",
    #     "CL":"1",
    #     "DOID":"2",
    #     "EFO":"16",
    #     "CVCL":"4"}
    # ont_id_to_og = {x:load_ontology.load(x)[0] for x in list(ont_name_to_ont_id.values())}
    # pipeline = p_48()

    # TWO_CHAR_MAPPINGS_JSON = "/mnt/c/Users/togotv_dell1/work/biosample/MetaSRA-pipeline/map_sra_to_ontology/metadata/two_char_mappings.json"
    if keywords_f != "":
        with open(keywords_f, "r") as f:
            pipeline.stages[14].str_to_mappings = json.load(f)

    all_mappings = []
    ct = datetime.datetime.now()
    sys.stderr.write('[{}] Mapping with {} processes.\n'.format(ct, processes))
    if processes == 1:
    ## Simple and valid implementation.
        i = 0
        covered_query_map = dict()
        for tag_to_val in tag_to_vals:
            if i % 2 == 0 and debug_mode:
                ct = datetime.datetime.now()
                sys.stderr.write('[{}] {}\n'.format(ct, i))
            i += 1
            mapped_terms, real_props, covered_query_map = pipeline.run(tag_to_val, covered_query_map)
            mappings = {
                "mapped_terms": [x.to_dict() for x in mapped_terms],
                "real_value_properties": [x.to_dict() for x in real_props]
            }
            all_mappings.append(mappings)
    ## end

    ## Implementation with multiprocessing.Pool.
    else:
        # p = Pool(processes)
        # pipeline_results = p.map(pipeline.run, tag_to_vals)
        # for pipeline_result in pipeline_results:
        #     mappings = {
        #         "mapped_terms": [x.to_dict() for x in pipeline_result[0]],
        #         "real_value_properties": [x.to_dict() for x in pipeline_result[1]]
        #     }
        #     all_mappings.append(mappings)
        p = Pool(processes)
        size = len(tag_to_vals)/processes
        res = []
        for i in range(processes):
            sub_tag_to_vals = tag_to_vals[int(i*size):int((i+1)*size)]
            res.append(p.apply_async(pipeline.run_multiple, (sub_tag_to_vals,)))
        for r in res:
            all_mappings += r.get()
    ## end

    # ## Run pipeline for unique kv pairs.
    # all_mappings = []
    # kv_mapping = {}
    # ct = datetime.datetime.now()
    # sys.stderr.write('[{}] Mapping\n'.format(ct))
    # i = 0
    # for tag_to_val in tag_to_vals:
    #     if i % 2 == 0:
    #         ct = datetime.datetime.now()
    #         sys.stderr.write('[{}] {}\n'.format(ct, i))
    #     i += 1
    #     mappings = {}
    #     mappings["mapped_terms"] = []
    #     mappings["real_value_properties"] = []
    #     for k, v in tag_to_val.items():
    #         if (k, v) not in kv_mapping:
    #             mapped_terms, real_props = pipeline.run_kv(k, v)
    #             mapping = {
    #                 "mapped_terms": [x.to_dict() for x in mapped_terms],
    #                 "real_value_properties": [x.to_dict() for x in real_props]
    #             }
    #             kv_mapping[(k, v)] = mapping
    #         mappings["mapped_terms"] += kv_mapping[(k, v)]["mapped_terms"]
    #         mappings["real_value_properties"] += kv_mapping[(k, v)]["real_value_properties"]
    #     all_mappings.append(mappings)
    # ## end

    ct = datetime.datetime.now()
    sys.stderr.write('[{}] Run pipeline on key vals\n'.format(ct, processes))
    outputs = []
    for tag_to_val, mappings in zip(tag_to_vals, all_mappings):
        outputs.append(run_pipeline_on_key_vals(tag_to_val,
                                                ont_id_to_og,
                                                mappings))

    sys.stderr.write('[{}] Writing.\n'.format(ct))
    output_json = json.dumps(outputs, indent=4, separators=(',', ': '))
    if output_f != "":
        with open(output_f, mode='w') as f:
            f.write(output_json)
    else:
        print(output_json)
    sys.stderr.write('[{}] Done.\n'.format(ct))


def run_pipeline_on_key_vals(tag_to_val, ont_id_to_og, mapping_data): 
    
    mapped_terms = []
    real_val_props = []
    mapped_terms_details = []
    # remove "cell line", "disease", "treatment"
    exception_term_ids = ["EFO:0000322",
                          "DOID:4",
                          "EFO:0000727",
                          "EFO:0000408",
                          "Orphanet:377788"]
    for mapped_term_data in mapping_data["mapped_terms"]:
        term_id = mapped_term_data["term_id"]
        for ont in list(ont_id_to_og.values()):
            if term_id in ont.get_mappable_term_ids() and term_id not in exception_term_ids:
                mapped_terms.append(term_id)
                mapped_term_detail = mapped_term_data.copy()
                mapped_term_detail["term_name"] = ont.id_to_term[term_id].name
                mapped_terms_details.append(mapped_term_detail)
                break
    for real_val_data in mapping_data["real_value_properties"]:
        real_val_prop = {
            "unit_id":real_val_data["unit_id"], 
            "value":real_val_data["value"], 
            "property_id":real_val_data["property_id"],
            "original_key":real_val_data["original_key"], 
            "consequent":real_val_data["consequent"], 
            "path_to_mapping":real_val_data["path_to_mapping"]
        }
        real_val_props.append(real_val_prop)

    # Add super-terms of mapped terms to the list of ontology term features   
    sup_terms = set()
    for og in list(ont_id_to_og.values()):
        for term_id in mapped_terms:
            sup_terms.update(og.recursive_relationship(term_id, ['is_a', 'part_of']))
    mapped_terms = list(sup_terms)

    # commented out by shikeda
    # predicted, confidence = run_sample_type_predictor.run_sample_type_prediction(
    #     tag_to_val, 
    #     mapped_terms, 
    #     real_val_props
    # )
    # end

    mapping_data = {
        ## changed by shikeda
        # "mapped ontology terms": mapped_terms, 
        "mapped ontology terms": mapped_terms_details,
        "real-value properties": real_val_props}
        # "sample type": predicted, 
        # "sample-type confidence": confidence}
        ## end

    # added by shikeda
    accession = tag_to_val.get("accession")
    if accession:
        mapping_data["accession"] = accession
    # end

    return mapping_data
    #print json.dumps(mapping_data, indent=4, separators=(',', ': '))


def run_pipeline_on_key_vals_wrapper(args):
    return run_pipeline_on_key_vals(*args)

#def run_pipeline(tag_to_val, pipeline):
#    pipeline = p_48()
#    sample_acc_to_matches = {}
#    mapped_terms, real_props = pipeline.run(tag_to_val)
#    mappings = {
#        "mapped_terms":[x.to_dict() for x in mapped_terms], 
#        "real_value_properties": [x.to_dict() for x in real_props]
#    }
#    return mappings
    

def dd_init():
    return 1.0

def p_48():
    spec_lex = pc.SpecialistLexicon(config.specialist_lex_location())
    inflec_var = pc.SPECIALISTLexInflectionalVariants(spec_lex)
    spell_var = pc.SPECIALISTSpellingVariants(spec_lex)
    key_val_filt = pc.KeyValueFilter_Stage()
    init_tokens_stage = pc.InitKeyValueTokens_Stage()
    ngram = pc.NGram_Stage()
    lower_stage = pc.Lowercase_Stage()
    man_at_syn = pc.ManuallyAnnotatedSynonyms_Stage()
    infer_cell_line = pc.InferCellLineTerms_Stage()
    prop_spec_syn = pc.PropertySpecificSynonym_Stage()
    infer_dev_stage = pc.ImpliedDevelopmentalStageFromAge_Stage()
    linked_super = pc.LinkedTermsOfSuperterms_Stage()
    cell_culture = pc.ConsequentCulturedCell_Stage()
    filt_match_priority = pc.FilterOntologyMatchesByPriority_Stage()
    real_val = pc.ExtractRealValue_Stage()
    match_cust_targs = pc.ExactMatchCustomTargets_Stage()
    cust_conseq = pc.CustomConsequentTerms_Stage()
    delimit_plus = pc.Delimit_Stage('+')
    delimit_underscore = pc.Delimit_Stage('_')
    delimit_dash = pc.Delimit_Stage('-')
    delimit_slash = pc.Delimit_Stage('/')
    block_cell_line_key = pc.BlockCellLineNonCellLineKey_Stage()
    subphrase_linked = pc.RemoveSubIntervalOfMatchedBlockAncestralLink_Stage()
    cellline_to_implied_disease = pc.CellLineToImpliedDisease_Stage()
    acr_to_expan = pc.AcronymToExpansion_Stage()
    # exact_match = pc.ExactStringMatching_Stage(["1", "2", "4", "5", "7", "8", "9"], query_len_thresh=3)
    exact_match = pc.ExactStringMatching_Stage(["1", "2", "4", "5", "7", "8", "9", "19"], query_len_thresh=3)
    fuzzy_match = pc.FuzzyStringMatching_Stage(0.1, query_len_thresh=3)
    two_char_match = pc.TwoCharMappings_Stage()
    time_unit = pc.ParseTimeWithUnit_Stage()

    stages = [
        key_val_filt,
        init_tokens_stage,
        ngram,
        lower_stage,
        delimit_plus,
        delimit_underscore,
        delimit_dash,
        delimit_slash,
        inflec_var,
        spell_var,
        man_at_syn,
        acr_to_expan,
        time_unit,
        exact_match,
        two_char_match,
        prop_spec_syn,
        fuzzy_match,
        match_cust_targs,
        block_cell_line_key,
        linked_super,
        cellline_to_implied_disease,
        subphrase_linked,
        cust_conseq,
        real_val,
        filt_match_priority,
        infer_cell_line,
        infer_dev_stage,
        cell_culture]
    # return pc.Pipeline(stages, defaultdict(lambda: 1.0))
    return pc.Pipeline(stages, defaultdict(dd_init))


if __name__ == "__main__":
    main()
